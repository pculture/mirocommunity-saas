from django.conf.urls.defaults import patterns, include, url
from localtv.decorators import require_site_admin

from mirocommunity_saas.admin.forms import (EditSettingsForm, AuthorForm,
                                            AuthorFormSet, VideoFormSet)
from mirocommunity_saas.admin.views import (index, TierView, TierChangeView,
                                            DowngradeConfirmationView)


# Tier urls
urlpatterns = patterns('',
    url(r'^$', index, name='localtv_admin_index'),
    url(r'^upgrade/$',
        require_site_admin(TierView.as_view()),
        name='localtv_admin_tier'),
    url(r'^upgrade/confirm_downgrade/$',
        require_site_admin(DowngradeConfirmationView.as_view()),
        name='localtv_admin_tier_confirm'),
    url(r'^upgrade/complete/$',
        require_site_admin(TierChangeView.as_view()),
        name='localtv_admin_tier_change'),
    url(r'^paypal/', include('paypal.standard.ipn.urls')),
)

# Moderation overrides
urlpatterns += patterns('mirocommunity_saas.admin.approve_reject_views',
    url(r'^actions/approve_video/$', 'approve_video',
        name='localtv_admin_approve_video'),
    url(r'^actions/feature_video/$', 'feature_video',
        name='localtv_admin_feature_video'),
    url(r'^actions/approve_all/$', 'approve_all',
        name='localtv_admin_approve_all'),
)

# Live search overrides
urlpatterns += patterns('mirocommunity_saas.admin.livesearch_views',
    url(r'^add/approve/$', 'approve',
        name='localtv_admin_search_video_approve')
)

# Overrides for settings, users, and videos.
urlpatterns += patterns('localtv.admin',
    url(r'^settings/$', 'design_views.edit_settings',
        {'form_class': EditSettingsForm}, 'localtv_admin_settings'),
    url(r'^users/$', 'user_views.users',
        {'formset_class': AuthorFormSet, 'form_class': AuthorForm},
        'localtv_admin_users'),
    url(r'^bulk_edit/$', 'bulk_edit_views.bulk_edit',
        {'formset_class': VideoFormSet}, 'localtv_admin_bulk_edit')
)

# Theming overrides
urlpatterns += patterns(
    'mirocommunity_saas.admin.upload_views',
    url(r'^themes/$', 'index',
        name='uploadtemplate-index'),
    url(r'^themes/add/$', 'create',
        name='uploadtemplate-create'),
    url(r'^themes/(?P<pk>\d+)/edit$', 'update',
        name='uploadtemplate-update'),
    url(r'^themes/(\d+)/delete$', 'delete',
        name='uploadtemplate-delete'),
    url(r'^themes/unset_default$', 'unset_default',
        name='uploadtemplate-unset_default'),
    url(r'^themes/set_default/(\d+)$', 'set_default',
        name='uploadtemplate-set_default'))

# Flatpages overrides
urlpatterns += patterns('mirocommunity_saas.admin.flatpages_views',
    url(r'flatpages/$', 'flatpages_admin', name='localtv_admin_flatpages'),
)
