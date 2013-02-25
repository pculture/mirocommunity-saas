from django.conf import settings
from django.http import HttpResponse, Http404

from localtv.admin.livesearch.views import LiveSearchApproveVideoView
from localtv.decorators import require_site_admin, referrer_redirect
from localtv.models import Video

from mirocommunity_saas.models import SiteTierInfo

class TierLiveSearchApproveVideoView(LiveSearchApproveVideoView):

    def get(self, request, **kwargs):
        if not request.GET.get('queue'):
            try:
                tier = SiteTierInfo.objects.get_current().tier
            except SiteTierInfo.DoesNotExist:
                raise Http404
            if tier.video_limit is not None:
                video_count = Video.objects.filter(status=Video.ACTIVE,
                                                   site=settings.SITE_ID
                                          ).count()
                if video_count + 1 > tier.video_limit:
                    return HttpResponse(
                        content="You are over the video limit. You "
                        "will need to upgrade to approve "
                        "that video.", status=402)

        return LiveSearchApproveVideoView.get(self, request, **kwargs)

approve = referrer_redirect(require_site_admin(
        TierLiveSearchApproveVideoView.as_view()))
