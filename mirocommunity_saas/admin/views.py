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
import urllib

from django.conf import settings
from django.core.urlresolvers import reverse
from django.contrib import comments
from django.contrib.sites.models import Site
from django.http import HttpResponseRedirect, Http404
from django.shortcuts import render_to_response
from django.template.context import RequestContext
from django.views.generic import TemplateView, View
from localtv.decorators import require_site_admin
from localtv.models import Video
from paypal.standard.conf import (POSTBACK_ENDPOINT,
                                  SANDBOX_POSTBACK_ENDPOINT,
                                  RECEIVER_EMAIL)
from paypal.standard.forms import PayPalPaymentsForm

from mirocommunity_saas.models import SiteTierInfo, Tier
from mirocommunity_saas.utils.tiers import (check_tier_change_token,
                                            make_tier_change_token)


### Below this line
### ----------------------------------------------------------------------
### These are admin views that the user will see at /admin/*


@require_site_admin
def index(request):
    """
    Simple index page for the admin site.
    """
    tier = Tier.objects.get(sitetierinfo__site=settings.SITE_ID)
    site_videos = Video.objects.filter(site=settings.SITE_ID)
    total_count = site_videos.filter(status=Video.ACTIVE).count()
    week_ago = datetime.datetime.now() - datetime.timedelta(days=7)
    context = {
        'total_count': total_count,
        'percent_videos_used': math.floor((100.0 * total_count) /
                                          tier.video_limit),
        'videos_this_week_count': site_videos.filter(status=Video.ACTIVE,
                                                when_approved__gt=week_ago
                                            ).count(),
        'unreviewed_count': site_videos.filter(status=Video.UNAPPROVED
                                      ).count(),
        'comment_count': comments.get_model().objects.filter(is_public=False,
                                                             is_removed=False
                                                    ).count(),
    }
    return render_to_response('localtv/admin/index.html',
                              context,
                              context_instance=RequestContext(request))


class TierView(TemplateView):
    """
    Base class for views for changing tiers and confirming any Bad Things that
    might happen as a result.

    """
    form_class = PayPalPaymentsForm
    template_name = 'localtv/admin/upgrade.html'
    TOKEN_PARAM = 's'
    SLUG_PARAM = 'tier'

    def get(self, request, *args, **kwargs):
        self.forms = self.get_forms()
        return super(TierView, self).get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        forms = self.get_forms()
        # TODO: Flesh this out. There should be one valid form, and it should
        # be the only form passed into the context this time around. Also, it
        # should be accompanied by a bunch of notes about what the changes
        # will mean - they should only get here if the new tier is a downgrade
        # (or would otherwise represent a change in service.)


    def get_context_data(self, **kwargs):
        context = super(TierView, self).get_context_data(**kwargs)
        context.update({
            'forms': self.forms,
            'tier_info': self.tier_info,
            'paypal_url': POSTBACK_ENDPOINT,
            'paypal_sandbox_url': SANDBOX_POSTBACK_ENDPOINT,
            'use_paypal_sandbox': settings.PAYPAL_TEST

        })
        return context

    def get_forms(self):
        site = Site.objects.get_current()
        self.tier_info = SiteTierInfo.objects.get(site=site)
        self.tiers = self.tier_info.available_tiers.order_by('price')
        forms = dict((tier,
                      self.form_class(**self.get_form_kwargs(tier)))
                     for tier in self.tiers)
        return forms

    def get_form_kwargs(self, tier):
        kwargs = {'initial': self.get_initial(tier)}
        if self.request.method == 'POST':
            kwargs['data'] = self.request.POST
        return kwargs

    def get_initial(self, tier):
        """
        Returns a set of base initial data for a subscription to the given
        tier.

        """
        site = Site.objects.get_current()
        token = make_tier_change_token(tier)
        initial = {
            'cmd': '_xclick-subscriptions',
            'business': RECEIVER_EMAIL,
            # TODO: Should probably reference a url on the current site.
            'image_url': "http://www.mirocommunity.org/images/mc_logo.png",
            'a3': unicode(tier.price),
            'p3': '30',
            't3': 'D',
            'src': '1',
            'sra': '1',
            'cancel_return': 'http://{domain}{url}'.format(domain=site.domain,
                                           url=reverse('localtv_admin_tier')),
            'notify_url': 'http://{domain}{url}'.format(domain=site.domain,
                                                   url=reverse('paypal-ipn')),
            'return_url': 'http://{domain}{url}?{query}'.format(domain=site.domain,
                                    url=reverse('localtv_admin_tier_change'),
                                    query=urllib.urlencode({
                                        self.TOKEN_PARAM: token,
                                        self.SLUG_PARAM: tier.slug,
                                    })),
            'item_name': ("Miro Community subscription ({name} on "
                          "{domain})").format(name=tier.name,
                                              domain=site.domain),
            'invoice': tier.slug,
            'custom': "{name} for {domain}".format(name=tier.name,
                                                   domain=site.domain),
        }
        if self.tier_info.gets_free_trial:
            initial.update({
                'a1': '0',
                'p1': '30',
                't1': 'D'
            })
        return initial


class TierChangeView(View):
    """
    Changes the tier and redirects the user back to the admin tier view.

    """

    def dispatch(self, request, *args, **kwargs):
        tier_slug = request.GET.get(TierView.SLUG_PARAM, '')
        self.tier_info = SiteTierInfo.objects.get(site=settings.SITE_ID)

        try:
            self.tier = self.tier_info.available_tiers.get(slug=tier_slug)
        except Tier.DoesNotExist:
            raise Http404

        token = request.GET.get(TierView.TOKEN_PARAM, '')
        if not check_tier_change_token(self.tier, token):
            raise Http404

        return super(TierChangeView, self).dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        if self.tier_info.tier_id == self.tier.pk:
            # There shouldn't be a way to get here.
            raise Http404

        self.tier_info.tier = self.tier
        self.tier_info.tier_changed = datetime.datetime.now()
        self.tier_info.save()
        return HttpResponseRedirect(reverse('localtv_admin_tier'))

    def post(self, request, *args, **kwargs):
        return self.get(request, *args, **kwargs)
