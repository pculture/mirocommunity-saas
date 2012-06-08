DEBUG = False
TEMPLATE_DEBUG = DEBUG

ADMINS = (
	("Miro Community Devs", "dev@mirocommunity.org"),
)

MANAGERS = (
	("Miro Community Support", "support@mirocommunity.org"),
)

TIME_ZONE = 'UTC'
LANGUAGE_CODE = 'en-us'
SITE_ID = 1
USE_I18N = False
USE_L10N = True

MEDIA_URL = '/media/'
STATIC_URL = '/static/'

STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'compressor.finders.CompressorFinder',
)
TEMPLATE_LOADERS = (
    'uploadtemplate.loader.Loader',
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
)
MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.contrib.flatpages.middleware.FlatpageFallbackMiddleware',
    # Uncomment the next line for simple clickjacking protection:
    # 'django.middleware.clickjacking.XFrameOptionsMiddleware'
    'localtv.middleware.FixAJAXMiddleware',
    'localtv.middleware.UserIsAdminMiddleware',
    'openid_consumer.middleware.OpenIDMiddleware',
)

ROOT_URLCONF = 'mirocommunity_saas.urls'

UPLOADTEMPLATE_MEDIA_URL = MEDIA_URL + 'uploadtemplate/'
UPLOADTEMPLATE_STATIC_ROOTS = [] # other directories which have static files
UPLOADTEMPLATE_TEMPLATE_ROOTS = [] # other directories with templates

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.comments',
    'django.contrib.flatpages',
    'django.contrib.staticfiles',
    'django.contrib.markup',
    # Uncomment to use south migrations
    'south',
    'djpagetabs',
    'djvideo',
    'mirocommunity_saas',
    'localtv',
    'localtv.admin',
    'localtv.comments',
    'localtv.submit_video',
    'localtv.inline_edit',
    'localtv.user_profile',
    'localtv.playlists',
    'registration',
    'tagging',
    'uploadtemplate',
    'haystack',
    'email_share',
    'djcelery',
    'notification',
    'socialauth',
    'openid_consumer',
    'paypal.standard.ipn',
    'daguerre',
    'compressor',
    'mptt',
)

TEMPLATE_CONTEXT_PROCESSORS = (
    'django.core.context_processors.debug',
    'django.core.context_processors.i18n',
    'django.core.context_processors.media',
    'django.core.context_processors.static',
    'django.core.context_processors.request',
    'django.contrib.auth.context_processors.auth',
    'django.contrib.messages.context_processors.messages',
    "localtv.context_processors.localtv",
    "localtv.context_processors.browse_modules",
    "mirocommunity_saas.context_processors.tier_info",
)
PAYPAL_RECEIVER_EMAIL = 'donate@pculture.org'
AUTH_PROFILE_MODULE = 'user_profile.Profile'