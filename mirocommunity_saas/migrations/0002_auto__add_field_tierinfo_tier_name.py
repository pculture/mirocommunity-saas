# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding field 'TierInfo.tier_name'
        db.add_column('localtv_tierinfo', 'tier_name',
                      self.gf('django.db.models.fields.CharField')(default='basic', max_length=255),
                      keep_default=False)

    def backwards(self, orm):
        # Deleting field 'TierInfo.tier_name'
        db.delete_column('localtv_tierinfo', 'tier_name')

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
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(2012, 5, 8, 16, 25, 54, 591114)'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Group']", 'symmetrical': 'False', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(2012, 5, 8, 16, 25, 54, 590959)'}),
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
            'use_original_date': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        'mirocommunity_saas.tierinfo': {
            'Meta': {'object_name': 'TierInfo', 'db_table': "'localtv_tierinfo'"},
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
            'tier_name': ('django.db.models.fields.CharField', [], {'default': "'basic'", 'max_length': '255'}),
            'user_has_successfully_performed_a_paypal_transaction': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'video_allotment_warning_sent': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'waiting_on_payment_until': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'})
        },
        'sites.site': {
            'Meta': {'ordering': "('domain',)", 'object_name': 'Site', 'db_table': "'django_site'"},
            'domain': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        }
    }

    complete_apps = ['mirocommunity_saas']