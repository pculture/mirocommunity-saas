from django.http import Http404

from mirocommunity_saas.models import TierInfo

from localtv.decorators import require_site_admin

from localtv.admin.design_views import (
    newsletter_settings as _newsletter_settings)

@require_site_admin
def newsletter_settings(request):
    tier_info = TierInfo.objects.get_current()
    if (tier_info.enforce_tiers() and
        not tier_info.get_tier().permit_newsletter()):
        raise Http404

    return _newsletter_settings(request)
