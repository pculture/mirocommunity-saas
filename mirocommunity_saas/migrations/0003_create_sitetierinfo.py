# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import DataMigration
from django.conf import settings
from django.db import models

class Migration(DataMigration):
    needed_by = (
        ("localtv", "0077_auto__del_tierinfo__del_field_sitesettings_tier_name"),
    )

    def forwards(self, orm):
        "Write your forwards methods here."
        Site = orm['sites.site']

        TierInfo = orm['localtv.tierinfo']
        SiteSettings = orm['localtv.sitesettings']
        Video = orm['localtv.video']

        Tier = orm['mirocommunity_saas.tier']
        SiteTierInfo = orm['mirocommunity_saas.sitetierinfo']

        site = Site.objects.get(pk=settings.SITE_ID)
        site_settings = SiteSettings.objects.get(site=site)
        tier_info = TierInfo.objects.get_or_create(
                                                  site_settings=site_settings)

        # If they have a cost override, they were an early adopter.
        # Otherwise, not.
        is_early_adopter = bool(getattr(settings, 'LOCALTV_COST_OVERRIDE',
                                        False))

        if is_early_adopter:
            available_tiers = {
                'basic': Tier.objects.get(slug='basic'),
                'plus': Tier.objects.get(slug='plus_early'),
                'premium': Tier.objects.get(slug='premium_early'),
                'max': Tier.objects.get(slug='max_early'),
            }
        else:
            available_tiers = {
                'basic': Tier.objects.get(slug='basic'),
                'plus': Tier.objects.get(slug='plus'),
                'premium': Tier.objects.get(slug='premium'),
                'max': Tier.objects.get(slug='max'),
            }

        tier = available_tiers[site_settings.tier_name]

        try:
            site_tier_info = SiteTierInfo.objects.get(site=site)
        except SiteTierInfo.DoesNotExist:
            site_tier_info = SiteTierInfo.objects.create(
                site=site,
                tier=tier,
                tier_changed=datetime.datetime.now(),
                enforce_payments=not getattr(settings, 'LOCALTV_SKIP_PAYPAL', False),
                welcome_email_sent=(datetime.datetime.now()
                                    if tier_info.already_sent_welcome_email
                                    else None),
                free_trial_ending_sent=(datetime.datetime.now()
                                    if tier_info.free_trial_warning_sent
                                    else None),
                video_limit_warning_sent=(datetime.datetime.now()
                                    if tier_info.video_allotment_warning_sent
                                    else None),
                video_count_when_warned=(Video.objects.filter(status=1,
                                                              site=site
                                                     ).count()
                                    if tier_info.video_allotment_warning_sent
                                    else None),
            )
            for tier in available_tiers:
                site_tier_info.available_tiers.add(tier)

    def backwards(self, orm):
        "Write your backwards methods here."
        raise Exception

    models = {
        'auth.group': {
            'Meta': {'object_name': 'Group'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'})
        },
        'auth.permission': {
            'Meta': {'ordering': "('content_type__app_label', 'content_type__model', 'codename')", 'unique_together': "(('content_type', 'codename'),)", 'object_name': 'Permission'},
            'codename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        'auth.user': {
            'Meta': {'object_name': 'User'},
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Group']", 'symmetrical': 'False', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'}),
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '30'})
        },
        'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        'ipn.paypalipn': {
            'Meta': {'object_name': 'PayPalIPN', 'db_table': "'paypal_ipn'"},
            'address_city': ('django.db.models.fields.CharField', [], {'max_length': '40', 'blank': 'True'}),
            'address_country': ('django.db.models.fields.CharField', [], {'max_length': '64', 'blank': 'True'}),
            'address_country_code': ('django.db.models.fields.CharField', [], {'max_length': '64', 'blank': 'True'}),
            'address_name': ('django.db.models.fields.CharField', [], {'max_length': '128', 'blank': 'True'}),
            'address_state': ('django.db.models.fields.CharField', [], {'max_length': '40', 'blank': 'True'}),
            'address_status': ('django.db.models.fields.CharField', [], {'max_length': '11', 'blank': 'True'}),
            'address_street': ('django.db.models.fields.CharField', [], {'max_length': '200', 'blank': 'True'}),
            'address_zip': ('django.db.models.fields.CharField', [], {'max_length': '20', 'blank': 'True'}),
            'amount': ('django.db.models.fields.DecimalField', [], {'default': '0', 'null': 'True', 'max_digits': '64', 'decimal_places': '2', 'blank': 'True'}),
            'amount1': ('django.db.models.fields.DecimalField', [], {'default': '0', 'null': 'True', 'max_digits': '64', 'decimal_places': '2', 'blank': 'True'}),
            'amount2': ('django.db.models.fields.DecimalField', [], {'default': '0', 'null': 'True', 'max_digits': '64', 'decimal_places': '2', 'blank': 'True'}),
            'amount3': ('django.db.models.fields.DecimalField', [], {'default': '0', 'null': 'True', 'max_digits': '64', 'decimal_places': '2', 'blank': 'True'}),
            'amount_per_cycle': ('django.db.models.fields.DecimalField', [], {'default': '0', 'null': 'True', 'max_digits': '64', 'decimal_places': '2', 'blank': 'True'}),
            'auction_buyer_id': ('django.db.models.fields.CharField', [], {'max_length': '64', 'blank': 'True'}),
            'auction_closing_date': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'auction_multi_item': ('django.db.models.fields.IntegerField', [], {'default': '0', 'null': 'True', 'blank': 'True'}),
            'auth_amount': ('django.db.models.fields.DecimalField', [], {'default': '0', 'null': 'True', 'max_digits': '64', 'decimal_places': '2', 'blank': 'True'}),
            'auth_exp': ('django.db.models.fields.CharField', [], {'max_length': '28', 'blank': 'True'}),
            'auth_id': ('django.db.models.fields.CharField', [], {'max_length': '19', 'blank': 'True'}),
            'auth_status': ('django.db.models.fields.CharField', [], {'max_length': '9', 'blank': 'True'}),
            'business': ('django.db.models.fields.CharField', [], {'max_length': '127', 'blank': 'True'}),
            'case_creation_date': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'case_id': ('django.db.models.fields.CharField', [], {'max_length': '14', 'blank': 'True'}),
            'case_type': ('django.db.models.fields.CharField', [], {'max_length': '24', 'blank': 'True'}),
            'charset': ('django.db.models.fields.CharField', [], {'max_length': '32', 'blank': 'True'}),
            'contact_phone': ('django.db.models.fields.CharField', [], {'max_length': '20', 'blank': 'True'}),
            'created_at': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'currency_code': ('django.db.models.fields.CharField', [], {'default': "'USD'", 'max_length': '32', 'blank': 'True'}),
            'custom': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'exchange_rate': ('django.db.models.fields.DecimalField', [], {'default': '0', 'null': 'True', 'max_digits': '64', 'decimal_places': '16', 'blank': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '64', 'blank': 'True'}),
            'flag': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'flag_code': ('django.db.models.fields.CharField', [], {'max_length': '16', 'blank': 'True'}),
            'flag_info': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'for_auction': ('django.db.models.fields.DecimalField', [], {'default': '0', 'null': 'True', 'max_digits': '64', 'decimal_places': '2', 'blank': 'True'}),
            'from_view': ('django.db.models.fields.CharField', [], {'max_length': '6', 'null': 'True', 'blank': 'True'}),
            'handling_amount': ('django.db.models.fields.DecimalField', [], {'default': '0', 'null': 'True', 'max_digits': '64', 'decimal_places': '2', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'initial_payment_amount': ('django.db.models.fields.DecimalField', [], {'default': '0', 'null': 'True', 'max_digits': '64', 'decimal_places': '2', 'blank': 'True'}),
            'invoice': ('django.db.models.fields.CharField', [], {'max_length': '127', 'blank': 'True'}),
            'ipaddress': ('django.db.models.fields.IPAddressField', [], {'max_length': '15', 'blank': 'True'}),
            'item_name': ('django.db.models.fields.CharField', [], {'max_length': '127', 'blank': 'True'}),
            'item_number': ('django.db.models.fields.CharField', [], {'max_length': '127', 'blank': 'True'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '64', 'blank': 'True'}),
            'mc_amount1': ('django.db.models.fields.DecimalField', [], {'default': '0', 'null': 'True', 'max_digits': '64', 'decimal_places': '2', 'blank': 'True'}),
            'mc_amount2': ('django.db.models.fields.DecimalField', [], {'default': '0', 'null': 'True', 'max_digits': '64', 'decimal_places': '2', 'blank': 'True'}),
            'mc_amount3': ('django.db.models.fields.DecimalField', [], {'default': '0', 'null': 'True', 'max_digits': '64', 'decimal_places': '2', 'blank': 'True'}),
            'mc_currency': ('django.db.models.fields.CharField', [], {'default': "'USD'", 'max_length': '32', 'blank': 'True'}),
            'mc_fee': ('django.db.models.fields.DecimalField', [], {'default': '0', 'null': 'True', 'max_digits': '64', 'decimal_places': '2', 'blank': 'True'}),
            'mc_gross': ('django.db.models.fields.DecimalField', [], {'default': '0', 'null': 'True', 'max_digits': '64', 'decimal_places': '2', 'blank': 'True'}),
            'mc_handling': ('django.db.models.fields.DecimalField', [], {'default': '0', 'null': 'True', 'max_digits': '64', 'decimal_places': '2', 'blank': 'True'}),
            'mc_shipping': ('django.db.models.fields.DecimalField', [], {'default': '0', 'null': 'True', 'max_digits': '64', 'decimal_places': '2', 'blank': 'True'}),
            'memo': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'next_payment_date': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'notify_version': ('django.db.models.fields.DecimalField', [], {'default': '0', 'null': 'True', 'max_digits': '64', 'decimal_places': '2', 'blank': 'True'}),
            'num_cart_items': ('django.db.models.fields.IntegerField', [], {'default': '0', 'null': 'True', 'blank': 'True'}),
            'option_name1': ('django.db.models.fields.CharField', [], {'max_length': '64', 'blank': 'True'}),
            'option_name2': ('django.db.models.fields.CharField', [], {'max_length': '64', 'blank': 'True'}),
            'outstanding_balance': ('django.db.models.fields.DecimalField', [], {'default': '0', 'null': 'True', 'max_digits': '64', 'decimal_places': '2', 'blank': 'True'}),
            'parent_txn_id': ('django.db.models.fields.CharField', [], {'max_length': '19', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '24', 'blank': 'True'}),
            'payer_business_name': ('django.db.models.fields.CharField', [], {'max_length': '127', 'blank': 'True'}),
            'payer_email': ('django.db.models.fields.CharField', [], {'max_length': '127', 'blank': 'True'}),
            'payer_id': ('django.db.models.fields.CharField', [], {'max_length': '13', 'blank': 'True'}),
            'payer_status': ('django.db.models.fields.CharField', [], {'max_length': '10', 'blank': 'True'}),
            'payment_cycle': ('django.db.models.fields.CharField', [], {'max_length': '32', 'blank': 'True'}),
            'payment_date': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'payment_gross': ('django.db.models.fields.DecimalField', [], {'default': '0', 'null': 'True', 'max_digits': '64', 'decimal_places': '2', 'blank': 'True'}),
            'payment_status': ('django.db.models.fields.CharField', [], {'max_length': '9', 'blank': 'True'}),
            'payment_type': ('django.db.models.fields.CharField', [], {'max_length': '7', 'blank': 'True'}),
            'pending_reason': ('django.db.models.fields.CharField', [], {'max_length': '14', 'blank': 'True'}),
            'period1': ('django.db.models.fields.CharField', [], {'max_length': '32', 'blank': 'True'}),
            'period2': ('django.db.models.fields.CharField', [], {'max_length': '32', 'blank': 'True'}),
            'period3': ('django.db.models.fields.CharField', [], {'max_length': '32', 'blank': 'True'}),
            'period_type': ('django.db.models.fields.CharField', [], {'max_length': '32', 'blank': 'True'}),
            'product_name': ('django.db.models.fields.CharField', [], {'max_length': '128', 'blank': 'True'}),
            'product_type': ('django.db.models.fields.CharField', [], {'max_length': '128', 'blank': 'True'}),
            'profile_status': ('django.db.models.fields.CharField', [], {'max_length': '32', 'blank': 'True'}),
            'protection_eligibility': ('django.db.models.fields.CharField', [], {'max_length': '32', 'blank': 'True'}),
            'quantity': ('django.db.models.fields.IntegerField', [], {'default': '1', 'null': 'True', 'blank': 'True'}),
            'query': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'reason_code': ('django.db.models.fields.CharField', [], {'max_length': '15', 'blank': 'True'}),
            'reattempt': ('django.db.models.fields.CharField', [], {'max_length': '1', 'blank': 'True'}),
            'receipt_id': ('django.db.models.fields.CharField', [], {'max_length': '64', 'blank': 'True'}),
            'receiver_email': ('django.db.models.fields.EmailField', [], {'max_length': '127', 'blank': 'True'}),
            'receiver_id': ('django.db.models.fields.CharField', [], {'max_length': '127', 'blank': 'True'}),
            'recur_times': ('django.db.models.fields.IntegerField', [], {'default': '0', 'null': 'True', 'blank': 'True'}),
            'recurring': ('django.db.models.fields.CharField', [], {'max_length': '1', 'blank': 'True'}),
            'recurring_payment_id': ('django.db.models.fields.CharField', [], {'max_length': '128', 'blank': 'True'}),
            'remaining_settle': ('django.db.models.fields.DecimalField', [], {'default': '0', 'null': 'True', 'max_digits': '64', 'decimal_places': '2', 'blank': 'True'}),
            'residence_country': ('django.db.models.fields.CharField', [], {'max_length': '2', 'blank': 'True'}),
            'response': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'retry_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'rp_invoice_id': ('django.db.models.fields.CharField', [], {'max_length': '127', 'blank': 'True'}),
            'settle_amount': ('django.db.models.fields.DecimalField', [], {'default': '0', 'null': 'True', 'max_digits': '64', 'decimal_places': '2', 'blank': 'True'}),
            'settle_currency': ('django.db.models.fields.CharField', [], {'max_length': '32', 'blank': 'True'}),
            'shipping': ('django.db.models.fields.DecimalField', [], {'default': '0', 'null': 'True', 'max_digits': '64', 'decimal_places': '2', 'blank': 'True'}),
            'shipping_method': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'subscr_date': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'subscr_effective': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'subscr_id': ('django.db.models.fields.CharField', [], {'max_length': '19', 'blank': 'True'}),
            'tax': ('django.db.models.fields.DecimalField', [], {'default': '0', 'null': 'True', 'max_digits': '64', 'decimal_places': '2', 'blank': 'True'}),
            'test_ipn': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'time_created': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'transaction_entity': ('django.db.models.fields.CharField', [], {'max_length': '7', 'blank': 'True'}),
            'transaction_subject': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'txn_id': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '19', 'blank': 'True'}),
            'txn_type': ('django.db.models.fields.CharField', [], {'max_length': '128', 'blank': 'True'}),
            'updated_at': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'username': ('django.db.models.fields.CharField', [], {'max_length': '64', 'blank': 'True'}),
            'verify_sign': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'})
        },
        'localtv.category': {
            'Meta': {'ordering': "['name']", 'unique_together': "(('slug', 'site'), ('name', 'site'))", 'object_name': 'Category'},
            'contest_mode': ('django.db.models.fields.DateTimeField', [], {'default': 'None', 'null': 'True'}),
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'logo': ('django.db.models.fields.files.ImageField', [], {'max_length': '100', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '80'}),
            'parent': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'child_set'", 'null': 'True', 'to': "orm['localtv.Category']"}),
            'site': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['sites.Site']"}),
            'slug': ('django.db.models.fields.SlugField', [], {'max_length': '50'})
        },
        'localtv.feed': {
            'Meta': {'unique_together': "(('feed_url', 'site'),)", 'object_name': 'Feed'},
            'auto_approve': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'auto_authors': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "'auto_feed_set'", 'blank': 'True', 'to': "orm['auth.User']"}),
            'auto_categories': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['localtv.Category']", 'symmetrical': 'False', 'blank': 'True'}),
            'auto_update': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'calculated_source_type': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '255', 'blank': 'True'}),
            'description': ('django.db.models.fields.TextField', [], {}),
            'etag': ('django.db.models.fields.CharField', [], {'max_length': '250', 'blank': 'True'}),
            'feed_url': ('django.db.models.fields.URLField', [], {'max_length': '200'}),
            'has_thumbnail': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_updated': ('django.db.models.fields.DateTimeField', [], {}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '250'}),
            'site': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['sites.Site']"}),
            'status': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'thumbnail_extension': ('django.db.models.fields.CharField', [], {'max_length': '8', 'blank': 'True'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'null': 'True', 'blank': 'True'}),
            'webpage': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True'}),
            'when_submitted': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'})
        },
        'localtv.feedimport': {
            'Meta': {'ordering': "['-start']", 'object_name': 'FeedImport'},
            'auto_approve': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_activity': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'source': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'imports'", 'to': "orm['localtv.Feed']"}),
            'start': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'status': ('django.db.models.fields.CharField', [], {'default': "'started'", 'max_length': '10'}),
            'total_videos': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'videos_imported': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'videos_skipped': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'})
        },
        'localtv.feedimporterror': {
            'Meta': {'object_name': 'FeedImportError'},
            'datetime': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_skip': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'message': ('django.db.models.fields.TextField', [], {}),
            'source_import': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'errors'", 'to': "orm['localtv.FeedImport']"}),
            'traceback': ('django.db.models.fields.TextField', [], {'blank': 'True'})
        },
        'localtv.feedimportindex': {
            'Meta': {'object_name': 'FeedImportIndex'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'index': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'source_import': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'indexes'", 'to': "orm['localtv.FeedImport']"}),
            'video': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['localtv.Video']", 'unique': 'True'})
        },
        'localtv.newslettersettings': {
            'Meta': {'object_name': 'NewsletterSettings'},
            'facebook_url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'intro': ('django.db.models.fields.CharField', [], {'max_length': '200', 'blank': 'True'}),
            'last_sent': ('django.db.models.fields.DateTimeField', [], {'null': 'True'}),
            'repeat': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'show_icon': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'site_settings': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['localtv.SiteSettings']", 'unique': 'True', 'db_column': "'sitelocation_id'"}),
            'status': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'twitter_url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True'}),
            'video1': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'newsletter1'", 'null': 'True', 'to': "orm['localtv.Video']"}),
            'video2': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'newsletter2'", 'null': 'True', 'to': "orm['localtv.Video']"}),
            'video3': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'newsletter3'", 'null': 'True', 'to': "orm['localtv.Video']"}),
            'video4': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'newsletter4'", 'null': 'True', 'to': "orm['localtv.Video']"}),
            'video5': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'newsletter5'", 'null': 'True', 'to': "orm['localtv.Video']"})
        },
        'localtv.originalvideo': {
            'Meta': {'object_name': 'OriginalVideo'},
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '250'}),
            'remote_thumbnail_hash': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '64'}),
            'remote_video_was_deleted': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'thumbnail_updated': ('django.db.models.fields.DateTimeField', [], {'blank': 'True'}),
            'thumbnail_url': ('django.db.models.fields.URLField', [], {'max_length': '400', 'blank': 'True'}),
            'video': ('django.db.models.fields.related.OneToOneField', [], {'related_name': "'original'", 'unique': 'True', 'to': "orm['localtv.Video']"})
        },
        'localtv.savedsearch': {
            'Meta': {'object_name': 'SavedSearch'},
            'auto_approve': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'auto_authors': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "'auto_savedsearch_set'", 'blank': 'True', 'to': "orm['auth.User']"}),
            'auto_categories': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['localtv.Category']", 'symmetrical': 'False', 'blank': 'True'}),
            'auto_update': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'has_thumbnail': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'query_string': ('django.db.models.fields.TextField', [], {}),
            'site': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['sites.Site']"}),
            'thumbnail_extension': ('django.db.models.fields.CharField', [], {'max_length': '8', 'blank': 'True'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'null': 'True', 'blank': 'True'}),
            'when_created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'})
        },
        'localtv.searchimport': {
            'Meta': {'ordering': "['-start']", 'object_name': 'SearchImport'},
            'auto_approve': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_activity': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'source': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'imports'", 'to': "orm['localtv.SavedSearch']"}),
            'start': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'status': ('django.db.models.fields.CharField', [], {'default': "'started'", 'max_length': '10'}),
            'total_videos': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'videos_imported': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'videos_skipped': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'})
        },
        'localtv.searchimporterror': {
            'Meta': {'object_name': 'SearchImportError'},
            'datetime': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_skip': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'message': ('django.db.models.fields.TextField', [], {}),
            'source_import': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'errors'", 'to': "orm['localtv.SearchImport']"}),
            'traceback': ('django.db.models.fields.TextField', [], {'blank': 'True'})
        },
        'localtv.searchimportindex': {
            'Meta': {'object_name': 'SearchImportIndex'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'index': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'source_import': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'indexes'", 'to': "orm['localtv.SearchImport']"}),
            'suite': ('django.db.models.fields.CharField', [], {'max_length': '30'}),
            'video': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['localtv.Video']", 'unique': 'True'})
        },
        'localtv.sitesettings': {
            'Meta': {'object_name': 'SiteSettings', 'db_table': "'localtv_sitelocation'"},
            'about_html': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'admins': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "'admin_for'", 'blank': 'True', 'to': "orm['auth.User']"}),
            'background': ('django.db.models.fields.files.ImageField', [], {'max_length': '100', 'blank': 'True'}),
            'comments_required_login': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'css': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'display_submit_button': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'footer_html': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'has_thumbnail': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'hide_get_started': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'logo': ('django.db.models.fields.files.ImageField', [], {'max_length': '100', 'blank': 'True'}),
            'playlists_enabled': ('django.db.models.fields.IntegerField', [], {'default': '1'}),
            'screen_all_comments': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'sidebar_html': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'site': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['sites.Site']", 'unique': 'True'}),
            'status': ('django.db.models.fields.IntegerField', [], {'default': '1'}),
            'submission_requires_login': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'tagline': ('django.db.models.fields.CharField', [], {'max_length': '4096', 'blank': 'True'}),
            'thumbnail_extension': ('django.db.models.fields.CharField', [], {'max_length': '8', 'blank': 'True'}),
            'tier_name': ('django.db.models.fields.CharField', [], {'default': "'basic'", 'max_length': '255'}),
            'use_original_date': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        'localtv.tierinfo': {
            'Meta': {'object_name': 'TierInfo'},
            'already_sent_tiers_compliance_email': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'already_sent_welcome_email': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'current_paypal_profile_id': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '255', 'blank': 'True'}),
            'free_trial_available': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'free_trial_started_on': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'free_trial_warning_sent': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'fully_confirmed_tier_name': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '255', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'in_free_trial': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'inactive_site_warning_sent': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'payment_due_date': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'payment_secret': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '255', 'blank': 'True'}),
            'should_send_welcome_email_on_paypal_event': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'site_settings': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['localtv.SiteSettings']", 'unique': 'True', 'db_column': "'sitelocation_id'"}),
            'user_has_successfully_performed_a_paypal_transaction': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'video_allotment_warning_sent': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'waiting_on_payment_until': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'})
        },
        'localtv.video': {
            'Meta': {'ordering': "['-when_submitted']", 'object_name': 'Video'},
            'authors': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "'authored_set'", 'blank': 'True', 'to': "orm['auth.User']"}),
            'calculated_source_type': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '255', 'blank': 'True'}),
            'categories': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['localtv.Category']", 'symmetrical': 'False', 'blank': 'True'}),
            'contact': ('django.db.models.fields.CharField', [], {'max_length': '250', 'blank': 'True'}),
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'embed_code': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'feed': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['localtv.Feed']", 'null': 'True', 'blank': 'True'}),
            'file_url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True'}),
            'file_url_length': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'file_url_mimetype': ('django.db.models.fields.CharField', [], {'max_length': '60', 'blank': 'True'}),
            'flash_enclosure_url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True'}),
            'guid': ('django.db.models.fields.CharField', [], {'max_length': '250', 'blank': 'True'}),
            'has_thumbnail': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_featured': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '250'}),
            'notes': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'search': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['localtv.SavedSearch']", 'null': 'True', 'blank': 'True'}),
            'site': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['sites.Site']"}),
            'status': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'thumbnail_extension': ('django.db.models.fields.CharField', [], {'max_length': '8', 'blank': 'True'}),
            'thumbnail_url': ('django.db.models.fields.URLField', [], {'max_length': '400', 'blank': 'True'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'null': 'True', 'blank': 'True'}),
            'video_service_url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True'}),
            'video_service_user': ('django.db.models.fields.CharField', [], {'max_length': '250', 'blank': 'True'}),
            'website_url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True'}),
            'when_approved': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'when_modified': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now', 'auto_now': 'True', 'db_index': 'True', 'blank': 'True'}),
            'when_published': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'when_submitted': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'})
        },
        'localtv.watch': {
            'Meta': {'object_name': 'Watch'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ip_address': ('django.db.models.fields.IPAddressField', [], {'max_length': '15'}),
            'timestamp': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'null': 'True', 'blank': 'True'}),
            'video': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['localtv.Video']"})
        },
        'localtv.widgetsettings': {
            'Meta': {'object_name': 'WidgetSettings'},
            'bg_color': ('django.db.models.fields.CharField', [], {'max_length': '20', 'blank': 'True'}),
            'bg_color_editable': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'border_color': ('django.db.models.fields.CharField', [], {'max_length': '20', 'blank': 'True'}),
            'border_color_editable': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'css': ('django.db.models.fields.files.FileField', [], {'max_length': '100', 'blank': 'True'}),
            'css_editable': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'has_thumbnail': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'icon': ('django.db.models.fields.files.ImageField', [], {'max_length': '100', 'blank': 'True'}),
            'icon_editable': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'site': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['sites.Site']", 'unique': 'True'}),
            'text_color': ('django.db.models.fields.CharField', [], {'max_length': '20', 'blank': 'True'}),
            'text_color_editable': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'thumbnail_extension': ('django.db.models.fields.CharField', [], {'max_length': '8', 'blank': 'True'}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '250', 'blank': 'True'}),
            'title_editable': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        'mirocommunity_saas.sitetierinfo': {
            'Meta': {'object_name': 'SiteTierInfo'},
            'available_tiers': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'site_available_set'", 'symmetrical': 'False', 'to': "orm['mirocommunity_saas.Tier']"}),
            'enforce_payments': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'free_trial_ending_sent': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ipn_set': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['ipn.PayPalIPN']", 'symmetrical': 'False', 'blank': 'True'}),
            'site': ('django.db.models.fields.related.OneToOneField', [], {'related_name': "'tier_info'", 'unique': 'True', 'to': "orm['sites.Site']"}),
            'site_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'tier': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['mirocommunity_saas.Tier']"}),
            'tier_changed': ('django.db.models.fields.DateTimeField', [], {}),
            'video_count_when_warned': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'video_limit_warning_sent': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'welcome_email_sent': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'})
        },
        'mirocommunity_saas.tier': {
            'Meta': {'object_name': 'Tier'},
            'admin_limit': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'ads_allowed': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'custom_css': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'custom_domain': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'custom_themes': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '30'}),
            'newsletter': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'price': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.SlugField', [], {'unique': 'True', 'max_length': '30'}),
            'video_limit': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True', 'blank': 'True'})
        },
        'sites.site': {
            'Meta': {'ordering': "('domain',)", 'object_name': 'Site', 'db_table': "'django_site'"},
            'domain': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        'tagging.tag': {
            'Meta': {'ordering': "('name',)", 'object_name': 'Tag'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '50', 'db_index': 'True'})
        },
        'tagging.taggeditem': {
            'Meta': {'unique_together': "(('tag', 'content_type', 'object_id'),)", 'object_name': 'TaggedItem'},
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'object_id': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'tag': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'items'", 'to': "orm['tagging.Tag']"})
        }
    }

    complete_apps = ['localtv', 'mirocommunity_saas']
    symmetrical = True
