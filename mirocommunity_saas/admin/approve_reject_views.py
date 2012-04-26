from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from localtv.models import Video
from localtv.decorators import require_site_admin
from localtv.admin.approve_reject_views import (
    approve_video as _approve_video,
    feature_video as _feature_video,
    approve_all as _approve_all,
    get_video_paginator)

from mirocommunity_saas.models import TierInfo

VIDEO_LIMIT_ERROR = ("You are over the video limit. You will need to upgrade "
                     "to approve that video.")

@require_site_admin
def approve_video(request):
    tier_info = TierInfo.objects.get_current()
    # If the site would exceed its video allotment, then fail with a HTTP 402
    # and a clear message about why.
    if (tier_info.enforce_tiers() and
        tier_info.get_tier().remaining_videos() < 1):
        return HttpResponse(
            content=VIDEO_LIMIT_ERROR,
            status=402)
    return _approve_video(request)

@require_site_admin
def feature_video(request):
    tier_info = TierInfo.objects.get_current()
    current_video = get_object_or_404(Video, pk=request.GET.get('video_id'),
                                      site=tier_info.site_settings.site)
    if current_video.status != Video.ACTIVE:
        if (tier_info.enforce_tiers() and
            tier_info.get_tier().remaining_videos() < 1):
            return HttpResponse(
                content=VIDEO_LIMIT_ERROR,
                status=402)
    return _feature_video(request)

@require_site_admin
def approve_all(request):
    tier_info = TierInfo.objects.get_current()

    video_paginator = get_video_paginator(tier_info.site_settings)
    try:
        page = video_paginator.page(int(request.GET.get('page', 1)))
    except Exception:
        # let the other view handle it
        return _approve_all(request)

    if tier_info.enforce_tiers():
        tier_remaining_videos = tier_info.get_tier().remaining_videos()
        if len(page.object_list) > tier_remaining_videos:
            remaining = tier_remaining_videos
            need = len(page.object_list)
            return HttpResponse(content=(
                    "You are trying to approve %(need)i videos at a time. "
                    "However, you can approve only %(remaining)i more videos "
                    "under your video limit. Please upgrade your account to "
                    "increase your limit, or unapprove some older videos to "
                    "make space for newer ones.") % {
                    'need': need,
                    'remaining': remaining},
                                status=402)
