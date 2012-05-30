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

from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, Http404
from django.views.generic import TemplateView, View
from localtv.admin.views import IndexView
from localtv.decorators import require_site_admin
from uploadtemplate.models import Theme

from mirocommunity_saas.admin.forms import TierChangeForm
from mirocommunity_saas.models import SiteTierInfo, Tier
from mirocommunity_saas.utils.tiers import (check_tier_change_token,
                                            make_tier_change_token,
                                            admins_to_demote,
                                            videos_to_deactivate)


class TierIndexView(IndexView):
    def get_context_data(self, **kwargs):
        context = super(TierIndexView, self).get_context_data(**kwargs)
        tier = SiteTierInfo.objects.get_current().tier
        context.update({
            'percent_videos_used': math.floor((100.0 * context['total_count'])
                                              / tier.video_limit),
        })
        return context


index = require_site_admin(TierIndexView.as_view())


class BaseTierView(TemplateView):
    """
    Base class for views that handle tier changes.

    """
    form_class = TierChangeForm
    TOKEN_PARAM = 's'
    SLUG_PARAM = 'tier'

    def get_tier_form(self, tier):
        return self.form_class(tier, **self.get_tier_form_kwargs(tier))

    def get_tier_form_kwargs(self, tier):
        return {
            'return_params': {self.TOKEN_PARAM: make_tier_change_token(tier),
                              self.SLUG_PARAM: tier.slug},
        }


class TierView(BaseTierView):
    """
    Base class for views for changing tiers and confirming any Bad Things that
    might happen as a result.

    """
    template_name = 'localtv/admin/upgrade.html'

    def get(self, request, *args, **kwargs):
        self.forms = self.get_forms()
        return super(TierView, self).get(request, *args, **kwargs)


    def get_context_data(self, **kwargs):
        context = super(TierView, self).get_context_data(**kwargs)
        context.update({
            'forms': self.forms,
            'tier_info': self.tier_info,
        })
        return context

    def get_forms(self):
        self.tier_info = SiteTierInfo.objects.get_current()
        self.tiers = self.tier_info.available_tiers.order_by('price')
        forms = dict((tier, self.get_tier_form(tier))
                     for tier in self.tiers)
        return forms

    def get_tier_form_kwargs(self, tier):
        kwargs = super(TierView, self).get_tier_form_kwargs(tier)
        kwargs['confirm_params'] = {self.SLUG_PARAM: tier.slug}
        return kwargs


class DowngradeConfirmationView(BaseTierView):
    template_name = 'localtv/admin/downgrade_confirm.html'

    def get_context_data(self, **kwargs):
        context = BaseTierView.get_context_data(self)
        tier_info = SiteTierInfo.objects.get_current()
        slug = self.request.GET.get(self.SLUG_PARAM, '')
        try:
            tier = tier_info.available_tiers.get(slug=slug)
        except Tier.DoesNotExist:
            raise Http404
        context.update({
            'form': self.get_tier_form(tier),
            'tier': tier,
            'tier_info': tier_info,
            'admins_to_demote': admins_to_demote(tier),
            'videos_to_deactivate': videos_to_deactivate(tier),
            'have_theme': Theme.objects.filter(default=True).exists()
        })
        return context


class TierChangeView(View):
    """
    Changes the tier and redirects the user back to the admin tier view.

    """
    def finished(self):
        """
        Since this is an intermediate view, we return the user to the same
        place whether or not we've actually done anything.

        """
        return HttpResponseRedirect(reverse('localtv_admin_tier'))

    def dispatch(self, request, *args, **kwargs):
        tier_slug = request.GET.get(TierView.SLUG_PARAM, '')
        self.tier_info = SiteTierInfo.objects.get_current()

        try:
            self.tier = self.tier_info.available_tiers.get(slug=tier_slug)
        except Tier.DoesNotExist:
            return self.finished()

        token = request.GET.get(TierView.TOKEN_PARAM, '')
        if not check_tier_change_token(self.tier, token):
            return self.finished()

        return super(TierChangeView, self).dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        if self.tier_info.tier_id != self.tier.pk:
            self.tier_info.tier = self.tier
            self.tier_info.tier_changed = datetime.datetime.now()
            self.tier_info.save()
        return self.finished()

    def post(self, request, *args, **kwargs):
        return self.get(request, *args, **kwargs)
