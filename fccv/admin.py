from django.contrib import admin

from django.contrib.comments.admin import CommentsAdmin
from django.contrib.comments.models import Comment

from fccv.models import BannedIP, Blacklist, Phrase

class BannedIPAdmin(admin.ModelAdmin):
    pass

class PhraseInline(admin.TabularInline):
    model = Phrase

class BlacklistAdmin(admin.ModelAdmin):
    search_fields = ('name', 'suspect__', 'timestamp')
    inlines = [PhraseInline,]

admin.site.register(Blacklist, BlacklistAdmin)
admin.site.register(BannedIP, BannedIPAdmin)

# Override default Comment admin to allow batch changes
class BatchCommentsAdmin(CommentsAdmin):
    actions = ['ban_ip_addresses', 'delete_selected', 'mark_not_public', 'mark_public', 'mark_not_removed', 'mark_removed']
    list_display = ('name', 'submit_date', 'link_to_item', 'content_type', 'object_pk', 'ip_address', 'is_public', 'is_removed')
    
    def link_to_item(self, obj):
        """
        Add a link to the related item in comments' list
        """
        item = obj.content_object
        return u'<a href="../../%s/%s/%s/" title="Access in admin">%s</a>' % (\
                                   item.__class__._meta.app_label,
                                   item.__class__._meta.module_name,
                                   item.id, 
                                   item)
    link_to_item.short_description = u'Commented Item'
    link_to_item.allow_tags = True
    
    def mark_not_public(self, request, queryset):
        queryset.update(is_public=False)
        self.message_user(request, "Marked %d comments not public." % queryset.count())
    
    def mark_public(self, request, queryset):
        queryset.update(is_public=True)
        self.message_user(request, "Marked %d comments public." % queryset.count())
    
    def mark_not_removed(self, request, queryset):
        queryset.update(is_removed=False)
        self.message_user(request, "Marked %d comments not removed." % queryset.count())
    
    def mark_removed(self, request, queryset):
        queryset.update(is_removed=True)
        self.message_user(request, "Marked %d comments removed." % queryset.count())
    
    def ban_ip_addresses(self, request, queryset):
        existing_addresses = set()
        new_addresses = set()
        for comment in queryset.all():
            if comment.ip_address in existing_addresses or comment.ip_address in new_addresses:
                continue
            banned_ip, created = BannedIP.objects.get_or_create(ip_address=comment.ip_address)
            if created:
                new_addresses.add(banned_ip.ip_address)
            else:
                existing_addresses.add(banned_ip.ip_address)
        new = len(new_addresses)
        existing = len(existing_addresses)
        self.message_user(request, "Banned %d new IP address%s.%s" % (new, new != 1 and 'es' or '', existing and (' %d %s already banned.' % (existing, existing == 1 and 'was' or 'were')) or ''))

admin.site.unregister(Comment)
admin.site.register(Comment, BatchCommentsAdmin)
