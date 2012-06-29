from django.db import models
from django.utils.translation import ugettext_lazy as _

class BannedIP(models.Model):
    ip_address = models.IPAddressField()
    
    def __unicode__(self):
        return u"%s" % self.ip_address
    
    class Meta:
        ordering = ('ip_address',)
        verbose_name = 'Banned IP'
        verbose_name_plural = 'Banned IPs'

class Blacklist(models.Model):
    """
    A list of words or phrases likely to appear in a certain category of spam.
    """
    name = models.CharField(max_length=100, help_text=u"""The name of the blacklist, e.g. 'drugs' or 'porn'.""")
    weight = models.FloatField(default=1.0, help_text=_(u"""Any score from this blacklist will be multiplied by this value; the default of 1 means the score will be used as is."""))
    
    class Meta:
        ordering = ('name', '-weight')
    
    def __unicode__(self):
        return u"Blacklist: %s" % self.name

class Phrase(models.Model):
    """A word or phrase likely to appear in a certain category of spam."""
    blacklist = models.ForeignKey(Blacklist, related_name='phrases')
    phrase = models.CharField(max_length=100)
    
    class Meta:
        ordering = ('blacklist', 'phrase')
        unique_together = ('blacklist', 'phrase')
    
    def __unicode__(self):
        return self.phrase

