# Miro Community - Easiest way to make a video website
#
# Copyright (C) 2010, 2011, 2012 Participatory Culture Foundation
#
# Miro Community is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your
# option) any later version.
#
# Miro Community is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Miro Community.  If not, see <http://www.gnu.org/licenses/>.

import datetime
import math

from django.conf import settings
from django.core.urlresolvers import reverse
from django.contrib import comments
from django.http import (HttpResponseRedirect, HttpResponseForbidden,
                         HttpResponse)
from django.shortcuts import render_to_response
from django.template.context import RequestContext
from django.template.loader import render_to_string
from django.views.decorators.csrf import csrf_protect, csrf_exempt
from localtv.decorators import require_site_admin
from localtv.models import SiteSettings, Video
from paypal.standard.ipn.models import PayPalIPN
from paypal.standard.ipn.signals import subscription_signup, subscription_cancel, subscription_eot, subscription_modify, payment_was_successful
import paypal.standard.ipn.views

from mirocommunity_saas import tiers, zendesk
from mirocommunity_saas.models import TierInfo


### Below this line
### ----------------------------------------------------------------------
### These are admin views that the user will see at /admin/*


@require_site_admin
def index(request):
    """
    Simple index page for the admin site.
    """
    site_settings = SiteSettings.objects.get_current()
    total_count = tiers.current_videos_that_count_toward_limit().count()
    percent_videos_used = math.floor(
        (100.0 * total_count) / site_settings.tierinfo.get().videos_limit())
    videos_this_week_count = Video.objects.filter(
        status=Video.ACTIVE,
        when_approved__gt=(datetime.datetime.utcnow() - datetime.timedelta(days=7))
        ).count()
    return render_to_response(
        'localtv/admin/index.html',
        {'total_count': total_count,
         'percent_videos_used': percent_videos_used,
         'unreviewed_count': Video.objects.filter(
                status=Video.UNAPPROVED,
                site=site_settings.site).count(),
         'videos_this_week_count': videos_this_week_count,
         'comment_count': comments.get_model().objects.filter(
                is_public=False, is_removed=False).count()},
        context_instance=RequestContext(request))


@require_site_admin
@csrf_protect
def confirmed_change_tier(request):
    '''The point of this function is to provide somewhere for the PayPal form to POST
    to -- instead of PayPal. So we start by asserting that PayPal is skipped, and then
    we simply change the tier, and redirect back to the site level admin page.'''
    skip_paypal = getattr(settings, "LOCALTV_SKIP_PAYPAL", False)
    assert skip_paypal

    target_tier_name = request.POST.get('target_tier_name', '')

    # validate
    if target_tier_name not in dict(tiers.CHOICES):
        # Always redirect back to tiers page
        return HttpResponseRedirect(reverse('localtv_admin_tier'))

    return _actually_switch_tier(target_tier_name)


@require_site_admin
def downgrade_confirm(request):
    target_tier_name = request.POST.get('target_tier_name', None)
    # validate
    if target_tier_name in dict(tiers.CHOICES):
        target_tier_obj = tiers.Tier(target_tier_name)

        would_lose = tiers.user_warnings_for_downgrade(target_tier_name)
        data = {}
        data['tier_name'] = target_tier_name
        data['paypal_sandbox'] = getattr(settings, 'PAYPAL_TEST', False)
        data['can_modify'] = _generate_can_modify()[target_tier_name]
        data['paypal_url'] = get_paypal_form_submission_url()
        data['paypal_email'] = tiers.get_paypal_email_address()
        data['paypal_email_acct'] = tiers.get_paypal_email_address()
        data['target_tier_obj'] = target_tier_obj
        data['would_lose_admin_usernames'] = tiers.push_number_of_admins_down(target_tier_obj.admins_limit())
        data['customtheme_nag'] = ('customtheme' in would_lose)
        data['advertising_nag'] = ('advertising' in would_lose)
        data['customdomain_nag'] = ('customdomain' in would_lose)
        data['css_nag'] = ('css' in would_lose)
        data['videos_nag'] = ('videos' in would_lose)
        data['videos_over_limit'] = tiers.hide_videos_above_limit(target_tier_obj)
        data['new_theme_name'] = tiers.switch_to_a_bundled_theme_if_necessary(target_tier_obj)
        data['payment_secret'] = SiteSettings.objects.get_current().tierinfo.get_payment_secret()
        return render_to_response('localtv/admin/downgrade_confirm.html', data,
                                  context_instance=RequestContext(request))

    # In some weird error case, redirect back to tiers page
    return HttpResponseRedirect(reverse('localtv_admin_tier'))


@require_site_admin
@csrf_protect
def upgrade(request):
    SWITCH_TO = 'Switch to this'
    UPGRADE = 'Upgrade Your Account'

    switch_messages = {}
    tier_info = TierInfo.objects.get_current()
    if tier_info.tier_name in ('premium', 'max'):
        switch_messages['plus'] = SWITCH_TO
    else:
        switch_messages['plus'] = UPGRADE

    if tier_info.tier_name == 'max':
        switch_messages['premium'] = SWITCH_TO
    else:
        switch_messages['premium'] = UPGRADE

    # Would you lose anything?
    would_lose = {}
    for tier_name in ['basic', 'plus', 'premium', 'max']:
        if tier_name == tier_info.tier_name:
            would_lose[tier_name] = False
        else:
            would_lose[tier_name] = tiers.user_warnings_for_downgrade(tier_name)

    upgrade_extra_payments = {}
    for target_tier_name in ['basic', 'plus', 'premium', 'max']:
        if (tier_info.in_free_trial or
            (tiers.Tier(target_tier_name).dollar_cost() <=
             tier_info.get_tier().dollar_cost()) or
            not tier_info.payment_due_date):
            upgrade_extra_payments[target_tier_name] = None
            continue
        upgrade_extra_payments[target_tier_name] = generate_payment_amount_for_upgrade(
            tier_info.tier_name, target_tier_name,
            tier_info.payment_due_date)

    data = {
        'upgrade_extra_payments': upgrade_extra_payments,
        'can_modify_mapping': _generate_can_modify(),
        'tier_info': tier_info,
        'would_lose_for_tier': would_lose,
        'switch_messages': switch_messages,
        'payment_secret': tier_info.get_payment_secret(),
        'offer_free_trial': tier_info.free_trial_available,
        'skip_paypal': getattr(settings, 'LOCALTV_SKIP_PAYPAL', False),
        'paypal_email_acct': tiers.get_paypal_email_address(),
        'tier_to_price': tiers.Tier.NAME_TO_COST(),
    }
    if not data['skip_paypal']:
        data['paypal_url'] = get_paypal_form_submission_url()

    return render_to_response('localtv/admin/upgrade.html', data,
                              context_instance=RequestContext(request))


### Below this line:
### -------------------------------------------------------------------------
### These functions are resquest handlers that actually switch tier.


@csrf_exempt
def paypal_return(request, payment_secret, target_tier_name):
    '''This view is where PayPal sends users to upon success. Some things to note:

    * PayPal sends us an "auth" parameter that we cannot validate.
    * This should be a POST so that cross-site scripting can't just upgrade people's sites.

    Therefore:

    * We use the payment_secret internal state as an anti-csrf value.
    * It is a GET for simplicity from PayPal.
    * A tricky site admin can exploit this, but that would just cause fully_confirmed_tier_name
      and tier_name to disagree, which is caught by our nightly checks.

    If you want to exploit a MC site and change its tier, and you can cause an admin
    with a cookie that's logged-in to visit pages you want, and you can steal the csrf value,
    your exploit will get caught during the nightly check for fully_confirmed_tier_name != tier_name.'''
    if payment_secret == SiteSettings.objects.get_current().tierinfo.payment_secret:
        return _paypal_return(target_tier_name)
    return HttpResponseForbidden("You submitted something invalid to this paypal return URL. If you are surprised to see this message, contact support@mirocommunity.org.")


def _paypal_return(target_tier_name):
    # This view always changes the tier_name stored in the TierInfo.
    # This is to that changes appear to happen immediately.
    #
    # However, it does not adjust the tierinfo.fully_confirmed_tier_name value.
    # That is only done by the IPN handlers.

    # What is the target tier name we are supposed to go to?
    # If it is the same as the current one, make no changes.
    tier_info = TierInfo.objects.get_current()
    if target_tier_name != tier_info.tier_name:
        # Leave a note in the fully_confirmed_tier_name of what we really are...
        tier_info.fully_confirmed_tier_name = tier_info.tier_name
        tier_info.tier_name = target_tier_name
        tier_info.save()
    return HttpResponseRedirect(reverse('localtv_admin_tier'))


@csrf_exempt
@require_site_admin
def begin_free_trial(request, payment_secret):
    '''This is where PayPal sends the user, if they are going to begin a free trial.

    At this stage, we do not know what tier the user wanted to opt into. That should be stored
    in the ?target_tier_name=... GET parameter.

    If it is some nonsense, we should show an obscure error message and tell them to email
    questions@MC if they got it.

    If it what we expect, then:

    * For now, trust that the IPN process will happen in the background,

    * Declare the free trial in-use, and

    * Switch the tier.'''
    # FIXME: This doesn't check the payment secret anymore.
    # That will be okay once we turn on PDT.
    #if payment_secret != site_settings.tierinfo.payment_secret:
    #    return HttpResponseForbidden("You are accessing this URL with invalid parameters. If you think you are seeing this message in error, email questions@mirocommunity.org")
    target_tier_name = request.GET.get('target_tier_name', '')
    if target_tier_name not in dict(tiers.CHOICES):
        return HttpResponse("Something went wrong switching your site level. Please send an email to questions@mirocommunity.org immediately.")

    # Switch the tier!
    return _start_free_trial_unconfirmed(target_tier_name)


### Below this line
### --------------------------------------------------------------------------------------------
### This function is something PayPal POSTs updates to.


@csrf_exempt
def ipn_endpoint(request, payment_secret):
    # PayPal sends data to this function via POST.
    #
    # At this point in processing, the data might be fake. Let's pass it to
    # the django-paypal code and ask it to verify it for us.
    site_settings = SiteSettings.objects.get_current()
    if (payment_secret == site_settings.tierinfo.payment_secret or
        payment_secret == site_settings.tierinfo.payment_secret.replace('/', '', 1)):
        response = paypal.standard.ipn.views.ipn(request)
        return response
    return HttpResponseForbidden("You submitted something invalid to this IPN handler.")


### Below this line
### ----------------------------------------------------------------------
### These are helper functions.


def get_paypal_form_submission_url():
    use_sandbox = getattr(settings, 'PAYPAL_TEST', False)
    if use_sandbox:
        return 'https://www.sandbox.paypal.com/cgi-bin/webscr'
    else: # Live API!
        return 'https://www.paypal.com/cgi-bin/webscr'


def generate_payment_amount_for_upgrade(start_tier_name, target_tier_name, current_payment_due_date, todays_date=None):
    target_tier_obj = tiers.Tier(target_tier_name)
    start_tier_obj = tiers.Tier(start_tier_name)

    if todays_date is None:
        todays_date = datetime.datetime.utcnow()
    
    days_difference = (current_payment_due_date - todays_date).days # note: this takes the floor() automatically
    if days_difference < 0:
        import logging
        logging.error("Um, the difference is less than zero. That's crazy.")
        days_difference = 0
    if days_difference == 0:
        return {'recurring': target_tier_obj.dollar_cost(),
                'cost_for_prorated_period': 0,
                'days_covered_by_prorating': 0}

    # Okay, so we have some days.
    # If it were the full price...
    price_difference = target_tier_obj.dollar_cost() - start_tier_obj.dollar_cost()
    # ...but we need to multiply by the proportion of the pay period this represents.
    # ...how much is that, anyway? Well, it's days_difference / days_in_the_pay_period
    # ...since our pay period is 30 days, that's easy.
    return {'recurring': target_tier_obj.dollar_cost(),
            'cost_for_prorated_period': int(price_difference * (days_difference / 30.0)),
            'days_covered_by_prorating': days_difference}


def _start_free_trial_unconfirmed(target_tier_name):
    '''We call this function from within the unconfirmed PayPal return
    handler, if you are just now starting a free trial.'''
    ti = TierInfo.objects.get_current()
    # If you already are in a free trial, just do a redirect back to the upgrade page.
    # This might happen if the IPN event fires *extremely* quickly.
    if ti.in_free_trial:
        return HttpResponseRedirect(reverse('localtv_admin_tier'))
    _start_free_trial_for_real(target_tier_name)
    return HttpResponseRedirect(reverse('localtv_admin_tier'))


def _start_free_trial_for_real(target_tier_name):
    ti = TierInfo.objects.get_current()
    # The point of this function is to set up the free trial, but to make
    # sure that when the IPN comes in, we still accept the information.
    if ti.payment_due_date is None:
        ti.payment_due_date = datetime.datetime.utcnow() + datetime.timedelta(days=30)
    ti.free_trial_started_on = datetime.datetime.utcnow()
    ti.in_free_trial = True
    ti.free_trial_available = False
    ti.tier_name = target_tier_name
    ti.save()
    return ti



def _actually_switch_tier(target_tier_name):
    # Proceed with the internal tier switch.

    # Sometimes, we let people jump forward before we detect the relevant IPN message.
    # When we do that, we stash the previous tier name into a TierInfo column called
    # fully_confirmed_tier_name. We only call _actually_switch_tier() when we
    # have confirmed a payment, so now is a good time to clear that column.
    ti = TierInfo.objects.get_current()
    fully_confirmed_tier_name = ti.fully_confirmed_tier_name
    ti.fully_confirmed_tier_name = '' # because we are setting it to this tier.
    ti.save()

    old_tier_name = ti.tier_name
    if ti.free_trial_started_on is None:
        ti = _start_free_trial_for_real(target_tier_name)
    # If the user *has* started a free trial, and this is an actual *change* in tier name,
    # then the trial must be over.
    else:
        if ((ti.in_free_trial and ((old_tier_name != target_tier_name) or
                                   (fully_confirmed_tier_name and (fully_confirmed_tier_name != target_tier_name))))):
            ti.in_free_trial = False
            ti.save()
    if target_tier_name == 'basic':
        # Delete the current paypal subscription ID
        ti.current_paypal_profile_id = ''
        ti.payment_due_date = None
        ti.save()

    if target_tier_name != ti.tier_name:
        ti.tier_name = target_tier_name
        ti.save()

    # Always redirect back to tiers page
    return HttpResponseRedirect(reverse('localtv_admin_tier'))


def _generate_can_modify():
    # This dictionary maps from the target_tier_name to the value of can_modify
    # In the PayPal API, you cannot modify your subscription in the following circumstances:
    # - you are permitting a free trial
    # - you are upgrading tier
    tier_info = TierInfo.objects.get_current()
    current_tier_price = tier_info.get_tier().dollar_cost()

    can_modify_mapping = {'basic': False}
    for target_tier_name in ['plus', 'premium', 'max']:
        if (tier_info.free_trial_available or tier_info.in_free_trial):
            can_modify_mapping[target_tier_name] = False
            continue
        target_tier_obj = tiers.Tier(target_tier_name)
        if target_tier_obj.dollar_cost() >= current_tier_price:
            can_modify_mapping[target_tier_name] = False
            continue
        can_modify_mapping[target_tier_name] = True

    return can_modify_mapping


def handle_recurring_profile_start(sender, **kwargs):
    ipn_obj = sender
    # If the thing is invalid, do not process any further.
    if ipn_obj.flag:
        return

    site_settings = SiteSettings.objects.get_current()
    tier_info = TierInfo.objects.get_current()
    current_confirmed_tier_obj = tier_info.get_fully_confirmed_tier()
    if current_confirmed_tier_obj:
        current_tier_obj = current_confirmed_tier_obj
    else:
        current_tier_obj = tier_info.get_tier()

    if tier_info.current_paypal_profile_id:
        # then we had better notify staff that the old one should be
        # cancelled.
        message_body = render_to_string('mirocommunity_saas/tiers_emails/disable_old_recurring_payment.txt',
                                        {'paypal_email_address': tiers.get_paypal_email_address(),
                                         'old_profile': tier_info.current_paypal_profile_id,
                                         'site_domain': site_settings.site.domain,
                                         'new_profile': ipn_obj.subscr_id})
        if tier_info.use_zendesk():
            zendesk.create_ticket("Eek, you should cancel a recurring payment profile",
                                          message_body, use_configured_assignee=True)

    expected_due_date = None
    # Okay. Now it's save to overwrite the subscription ID that is the current one.
    if tier_info.free_trial_available:
        tier_info.free_trial_available = False
    # Is this an upgrade that required an initial payment period?
    elif (tier_info.current_paypal_profile_id and
          float(ipn_obj.amount3) != current_tier_obj.dollar_cost() and
          ipn_obj.amount1 and float(ipn_obj.amount1)):
        # Validate the IPN: time period
        num, format = ipn_obj.period1.split(' ')
        num = int(num)
        if format.upper() != 'D':
            raise ValueError
        expected_due_date = ipn_obj.subscr_date + datetime.timedelta(days=num)
        if abs( (expected_due_date - tier_info.payment_due_date).days) > 2:
            raise ValueError, "There is something weird going on with the due date of the new subscription."
        # Validate the IPN: payment amount
        total_diff = float(ipn_obj.amount3) - current_tier_obj.dollar_cost()
        prorated_diff = (num / 30.0) * total_diff
        if int(ipn_obj.amount1) < int(prorated_diff):
            raise ValueError, "Monkey business."
    else:
        # Validate that there isn't a "trial" for no reason.
        if not tier_info.in_free_trial:
            # sanity-check that there is no period1 or period2 value
            paypal_event_contains_free_trial = ipn_obj.period1 or ipn_obj.period2
            if paypal_event_contains_free_trial and tier_info.use_zendesk():
                zendesk.create_ticket(
                    "Eek, the user tried to create a free trial incorrectly",
                    "Check on the state of the " + site_settings.site.domain + ""
                    " site",
                    use_configured_assignee=False)
                return

    tier_info.current_paypal_profile_id = ipn_obj.subscr_id
    tier_info.user_has_successfully_performed_a_paypal_transaction = True
    if expected_due_date:
        tier_info.payment_due_date = expected_due_date
    else:
        tier_info.payment_due_date = datetime.timedelta(days=30) + ipn_obj.subscr_date
    tier_info.save()

    # If we get the IPN, and we have not yet adjusted the tier name
    # to be at that level, now is a *good* time to do so.
    amount = float(ipn_obj.amount3)
    if current_tier_obj.dollar_cost() != amount:
        # Find the right tier to move to
        target_tier_name = tiers.Tier.get_by_cost(amount)
        _actually_switch_tier(target_tier_name)
subscription_signup.connect(handle_recurring_profile_start)


def on_subscription_cancel_switch_to_basic(sender, **kwargs):
    ipn_obj = sender

    # If the thing is invalid, do not process any further.
    if ipn_obj.flag:
        return

    # If the IPN object refers to a subscription ID other than the one that is ours,
    # stop immediately. This could happen if, say, they create a new subscription ID
    # (due to upgrading tier) and then cancelling the old one.
    #
    # That's exactly how we ask people to upgrade between tiers. Luckily, this
    # transition case is covered by the test suite.
    tier_info = TierInfo.objects.get_current()
    if tier_info.current_paypal_profile_id != ipn_obj.subscr_id:
        return

    _actually_switch_tier('basic')
subscription_cancel.connect(on_subscription_cancel_switch_to_basic)
subscription_eot.connect(on_subscription_cancel_switch_to_basic)


def handle_recurring_profile_modify(sender, **kwargs):
    ipn_obj = sender

    # If the thing is invalid, do not process any further.
    if ipn_obj.flag:
        return

    site_settings = SiteSettings.objects.get_current()
    tier_info = TierInfo.objects.get_current()

    if (tier_info.current_paypal_profile_id != sender.subscr_id) and (tier_info.use_zendesk()):
        # then we had better notify staff indicating that the old one
        # should be cancelled.
        message_body = render_to_string('mirocommunity_saas/tiers_emails/disable_old_recurring_payment.txt',
                                        {'paypal_email_address': tiers.get_paypal_email_address(),
                                         'profile_on_file': tier_info.current_paypal_profile_id,
                                         'site_domain': site_settings.site.domain,
                                         'surprising_profile': ipn_obj.subscr_id})
        zendesk.create_ticket("Eek, you should check on this MC site",
                                      message_body,
                                      use_configured_assignee=False)
        return

    # Okay, well at this point, we need to adjust the site tier to match.
    amount = float(ipn_obj.amount3)
    if tier_info.get_tier().dollar_cost() == amount:
        pass
    else:
        # Find the right tier to move to
        try:
            target_tier_name = tiers.Tier.get_by_cost(amount)
        except ValueError:
            # then we had better notify staff indicating that the
            # amount is bizarre.
            if tier_info.use_zendesk():
                message_body = render_to_string('mirocommunity_saas/tiers_emails/confused_modify_wrong_amount.txt',
                                                {'paypal_email_address': tiers.get_paypal_email_address(),
                                                 'profile_on_file': tier_info.current_paypal_profile_id,
                                                 'site_domain': site_settings.site.domain,
                                                 'surprising_profile': ipn_obj.subscr_id})
                zendesk.create_ticket("Eek, you should check on this MC site",
                                              message_body,
                                              use_configured_assignee=False)
            return
        _actually_switch_tier(target_tier_name)
subscription_modify.connect(handle_recurring_profile_modify)


def handle_successful_payment(sender, **kwargs):
    ipn_obj = sender

    # If the thing is invalid, do not process any further.
    if ipn_obj.flag:
        return

    test_ipn = getattr(settings, 'PAYPAL_TEST', False)

    if ipn_obj.test_ipn != test_ipn:
        # per Asheesh, make sure that the test_ipn setting matches the PAYPAL_TEST setting
        return

    tier_info = TierInfo.objects.get_current()
    current_tier_obj = tier_info.get_tier()

    if float(ipn_obj.payment_gross) != current_tier_obj.dollar_cost():
        raise ValueError("User paid %f instead of %f" % (ipn_obj.payment_gross,
                                                         current_tier_obj.dollar_cost()))

    subscription_start = PayPalIPN.objects.filter(
        subscr_id=ipn_obj.subscr_id,
        flag=False,
        test_ipn=test_ipn).exclude(period1="").order_by('-id')[0]
    num, format = subscription_start.period1.split(' ', 1)
    num = int(num)
    if format.upper() != 'D':
        raise ValueError('invalid repeat period: %r' % subscription_start.period1)

    tier_info.payment_due_date += datetime.timedelta(days=num)
    tier_info.save()
payment_was_successful.connect(handle_successful_payment)
