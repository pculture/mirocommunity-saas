from django.http import Http404

from mirocommunity_saas.models import TierInfo

from localtv import views

def newsletter(request):
    tier_info = TierInfo.objects.get_current()
    if (tier_info.enforce_tiers() and
        not tier_info.get_tier().permit_newsletter()):
        raise Http404

    return views.newsletter(request)
