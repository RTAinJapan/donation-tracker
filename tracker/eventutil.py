import json
import traceback
import urllib.request

from django.core import serializers
from django.db.models import Sum
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.urls.base import reverse

import tracker.models as models
import tracker.viewutil as viewutil

# TODO: this is 2018, we ought to be using requests


def post_donation_to_postbacks(donation):
    event_donations = models.Donation.objects.filter(
        event=donation.event.id, transactionstate='COMPLETED',
    )
    total = event_donations.aggregate(amount=Sum('amount'))['amount']

    if total is None:
        total = 0

    data = {
        'id': donation.id,
        'timereceived': str(donation.timereceived),
        'comment': donation.comment,
        'amount': float(donation.amount),
        'donor__visibility': donation.donor.visibility,
        'donor__visiblename': donation.donor.visible_name(),
        'new_total': float(total),
        'domain': donation.domain,
    }

    async_to_sync(get_channel_layer().group_send)(
        'donations', {'type': 'donation', **data}
    )

    try:
        data_json = json.dumps(
            data, ensure_ascii=False, cls=serializers.json.DjangoJSONEncoder
        ).encode('utf-8')

        postbacks = models.PostbackURL.objects.filter(event=donation.event)
        for postback in postbacks:
            opener = urllib.request.build_opener()
            req = urllib.request.Request(
                postback.url,
                data_json,
                headers={'Content-Type': 'application/json; charset=utf-8'},
            )
            opener.open(req, timeout=5)
    except Exception:
        viewutil.tracker_log(
            'postback_url', traceback.format_exc(), event=donation.event
        )


def make_paypal_return_url(donation: models.Donation):
    if donation.event.receivertype == 'msf2021' and donation.amount >= 1000:
        return reverse('tracker:paypal_return_msf2024s')
    return reverse('tracker:paypal_return')
