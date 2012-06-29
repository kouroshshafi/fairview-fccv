"""
Comment validation for Django 1.0+. It runs comments through a chain
of validators, which can be easily extended. Built-in checks include: one which 
derives its score from the number of links in a comment; one which checks if
the commenter's IP has been banned or has submitted questionable (non-public)
comments in the past; and one which compares the comment to a series of 
blacklists, deriving scores from the resulting Tanimoto coefficients and
the weights assigned to the blacklists.

To add more validators, configure FCCV_VALIDATORS in your Django 
settings, adding the path to any callable you want to use for scoring 
comments. A validator function should take two arguments -- the comment and 
the request -- and return either None, if it declines to make a call on the
comment, or a score between 0 and 1, indicating the probability that the 
comment is spam.

The scores from all validators are combined to determine whether a comment is
spam. There are two thresholds determining the disposition of a comment: if 
the comment scores above FCCV_PUBLIC_THRESHOLD, its is_public 
attribute will be set to False. If it scores above 
FCCV_REJECT_THRESHOLD, the request will be rejected outright.

"""
import logging
import operator
import re

from django.conf import settings
from django.contrib.comments.models import Comment
from django.contrib.comments.signals import comment_will_be_posted
from django.contrib.sites.models import Site
from django.core.exceptions import ImproperlyConfigured
from django.utils.html import strip_tags

from fccv.models import BannedIP, Blacklist

DEFAULT_FCCV_VALIDATORS = (
    'fccv.check_comment_email',
    'fccv.check_comment_ip',
    'fccv.check_comment_link_limit',
    'fccv.check_comment_name',
    'fccv.check_comment_text',
    'fccv.check_comment_url',
)

LINK_RE = re.compile(r'(https?://|href|mailto)')

SPLITTER = re.compile(r'\W+')

# from http://www.dcs.gla.ac.uk/idom/ir_resources/linguistic_utils/stop_words
STOP_WORDS = (
    'a', 'about', 'above', 'across', 'after', 'afterwards', 'again',
    'against', 'all', 'almost', 'alone', 'along', 'already', 'also',
    'although', 'always', 'am', 'among', 'amongst', 'amoungst', 'amount',
    'an', 'and', 'another', 'any', 'anyhow', 'anyone', 'anything', 'anyway',
    'anywhere', 'are', 'around', 'as', 'at', 'back', 'be', 'became',
    'because', 'become', 'becomes', 'becoming', 'been', 'before',
    'beforehand', 'behind', 'being', 'below', 'beside', 'besides', 'between',
    'beyond', 'bill', 'both', 'bottom', 'but', 'by', 'call', 'can', 'cannot',
    'cant', 'co', 'computer', 'con', 'could', 'couldnt', 'cry', 'de',
    'describe', 'detail', 'do', 'done', 'down', 'due', 'during', 'each', 'eg',
    'eight', 'either', 'eleven', 'else', 'elsewhere', 'empty', 'enough',
    'etc', 'even', 'ever', 'every', 'everyone', 'everything', 'everywhere',
    'except', 'few', 'fifteen', 'fify', 'fill', 'find', 'fire', 'first',
    'five', 'for', 'former', 'formerly', 'forty', 'found', 'four', 'from',
    'front', 'full', 'further', 'get', 'give', 'go', 'had', 'has', 'hasnt',
    'have', 'he', 'hence', 'her', 'here', 'hereafter', 'hereby', 'herein',
    'hereupon', 'hers', 'herself', 'him', 'himself', 'his', 'how', 'however',
    'hundred', 'i', 'ie', 'if', 'in', 'inc', 'indeed', 'interest', 'into',
    'is', 'it', 'its', 'itself', 'keep', 'last', 'latter', 'latterly',
    'least', 'less', 'ltd', 'made', 'many', 'may', 'me', 'meanwhile', 'might',
    'mill', 'mine', 'more', 'moreover', 'most', 'mostly', 'move', 'much',
    'must', 'my', 'myself', 'name', 'namely', 'neither', 'never',
    'nevertheless', 'next', 'nine', 'no', 'nobody', 'none', 'noone', 'nor',
    'not', 'nothing', 'now', 'nowhere', 'of', 'off', 'often', 'on', 'once',
    'one', 'only', 'onto', 'or', 'other', 'others', 'otherwise', 'our',
    'ours', 'ourselves', 'out', 'over', 'own', 'part', 'per', 'perhaps',
    'please', 'put', 'rather', 're', 'same', 'see', 'seem', 'seemed',
    'seeming', 'seems', 'serious', 'several', 'she', 'should', 'show', 'side',
    'since', 'sincere', 'six', 'sixty', 'so', 'some', 'somehow', 'someone',
    'something', 'sometime', 'sometimes', 'somewhere', 'still', 'such',
    'system', 'take', 'ten', 'than', 'that', 'the', 'their', 'them',
    'themselves', 'then', 'thence', 'there', 'thereafter', 'thereby',
    'therefore', 'therein', 'thereupon', 'these', 'they', 'thick', 'thin',
    'third', 'this', 'those', 'though', 'three', 'through', 'throughout',
    'thru', 'thus', 'to', 'together', 'too', 'top', 'toward', 'towards',
    'twelve', 'twenty', 'two', 'un', 'under', 'until', 'up', 'upon', 'us',
    'very', 'via', 'was', 'we', 'well', 'were', 'what', 'whatever', 'when',
    'whence', 'whenever', 'where', 'whereafter', 'whereas', 'whereby',
    'wherein', 'whereupon', 'wherever', 'whether', 'which', 'while',
    'whither', 'who', 'whoever', 'whole', 'whom', 'whose', 'why', 'will',
    'with', 'within', 'without', 'would', 'yet', 'you', 'your', 'yours',
    'yourself', 'yourselves',
)

def check_comment_email(comment, request):
    logger = logging.getLogger('fccv.check_comment_email')
    if comment.user_email:
        score = check_string(comment.user_email)
        return score
    return None

def check_comment_ip(comment, request):
    logger = logging.getLogger('fccv.check_comment_ip')
    try:
        banned = BannedIP.objects.get(ip_address=comment.ip_address)
        logger.info("""Comment from banned IP scores 1.0.""")
        return 1.0
    except:
        # each non-public comment from this IP counts against this one
        suspects = Comment.objects.filter(ip_address=comment.ip_address, is_public=False)
        score = min(suspects.count() / 10.0, 1.0)
        if score and settings.DEBUG:
            logger.debug("""Guilty by association with %s non-public comments from IP %s; score = %s.""" % (suspects.count(), comment.ip_address, score))
        return score

def check_comment_link_limit(comment, request):
    return check_link_limit(comment.comment)

def check_comment_name(comment, request):
    logger = logging.getLogger('fccv.check_comment_name')
    score = check_string(comment.user_name)
    return score

def check_comment_text(comment, request):
    return check_text(comment.comment)

def check_comment_url(comment, request):
    logger = logging.getLogger('fccv.check_comment_url')
    score = None
    if comment.user_url:
        score = check_string(comment.user_url)
        return score + .1
    return None

def check_link_limit(text):
    """Simple count of links in the comment."""
    logger = logging.getLogger('fccv.check_link_limit')
    link_count = len(LINK_RE.findall(text))
    score = min(link_count, 10.0) / 10.0
    if settings.DEBUG:
        logger.debug("""Text contained %s links; score = %s""" % (link_count, score))
    return score

def check_string(s):
    """Simple check to see if a string contains blacklisted words."""
    ls = s.lower()
    score = 0.0
    for blacklist in Blacklist.objects.select_related():
        for phrase in blacklist.phrases.all():
            if ls.find(phrase.phrase.lower()) == -1:
                continue
            else:
                score += .1
    return score
    
def check_text(text):
    """
    Returns the combined Tanimoto coefficients of the supplied text and 
    each of a set of predefined blacklists.
    """
    logger = logging.getLogger('fccv.check_blacklists')
    
    # process text into usable words
    text = text.lower()
    text = SPLITTER.sub(' ', text)
    words = set()
    for phrase in parse_phrases(text):
        if (len(phrase) > 2 
            and not phrase.isdigit()
            and not phrase == 'href'
            and not phrase.startswith('http') 
            and phrase not in STOP_WORDS
        ):
            words.add(phrase)
    if settings.DEBUG:
        logger.debug("""words from text: %s""" % words)
    
    score = 0.0
    for blacklist in Blacklist.objects.select_related():
        spam_phrases = set([phrase.phrase for phrase in blacklist.phrases.all()])
        if settings.DEBUG:
            logger.debug("""blacklist %s words: %s""" % (blacklist.name, spam_phrases))
        
        intersection = words & spam_phrases
        intersection_count = float(len(intersection))
        
        tc = intersection_count / (len(spam_phrases) + len(words) - intersection_count)
        
        weighted_score = max(0.0, min(1.0, tc * blacklist.weight))
        
        if settings.DEBUG:
            logger.debug("""Weighted score from blacklist %s: %s  TC: %s  Spam words in text: %s""" % (blacklist.name, weighted_score, tc, intersection))
        
        score += weighted_score
    
    score = max(0.0, min(1.0, score))
    if settings.DEBUG:
        logger.debug("""Combined score: %s""" % score)
    return score

def check_typepad_antispam(comment, request):
    logger = logging.getLogger('fccv.check_typepad_antispam')
    try:
        from akismet import Akismet
    except:
        return None
    
    if hasattr(settings, 'TYPEPAD_ANTISPAM_API_KEY'):
        ak = Akismet(
            key=settings.TYPEPAD_ANTISPAM_API_KEY,
            blog_url='http://%s/' % Site.objects.get(pk=settings.SITE_ID).domain
        )
        ak.baseurl = 'api.antispam.typepad.com/1.1/'
    else:
        ak = Akismet(
            key=settings.AKISMET_API_KEY,
            blog_url='http://%s/' % Site.objects.get(pk=settings.SITE_ID).domain
        )

    if ak.verify_key():
        data = {
            'user_ip': comment.ip_address,
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'referrer': request.META.get('HTTP_REFERER', ''),
            'comment_type': 'comment',
            'comment_author': comment.user_name.encode('utf-8'),
        }
        
        if ak.comment_check(comment.comment.encode('utf-8'), data=data, build_data=True):
            if settings.DEBUG:
                logger.debug("""TypePad AntiSpam thought this comment was spam.""")
            return .5
    
    return None

def parse_phrases(str):
    """
    Generator-based parsing of a search phrase into words
    and quote-delimited phrases. Handles single- and double-quoted
    phrases.
    """
    gen = iter(str)
    opener = ''
    word = ''
    for c in gen:
        if c == ' ':
            if opener:
                word += c
            elif word:
                yield word
                word = ''
        elif c == opener:
            opener = ''
            if word:
                yield word
                word = ''
        elif c == '"' or c == "'":
            opener = c
        else:
            word += c
    if word:
        yield word

def validate_comment(sender, comment, request, **kwargs):
    logger = logging.getLogger('fccv.validate_comment')
    validators = []
    for path in getattr(settings, 'FCCV_VALIDATORS', DEFAULT_FCCV_VALIDATORS):
        i = path.rfind('.')
        module, attr = path[:i], path[i+1:]
        try:
            mod = __import__(module, {}, {}, [attr])
        except ImportError, e:
            raise ImproperlyConfigured('Error importing comment validation module %s: "%s"' % (module, e))
        try:
            func = getattr(mod, attr)
        except AttributeError:
            raise ImproperlyConfigured('Module "%s" does not define a "%s" callable comment validator' % (module, attr))
        validators.append(func)
    
    reject_threshold = getattr(settings, 'FCCV_REJECT_THRESHOLD', 0.9)
    
    score = 0.0
    for validator in validators:
        validator_score = validator(comment, request)
        if settings.DEBUG:
            logger.debug("""Score from validator %s: %s""" % (validator, validator_score))
        if validator_score:
            score += validator_score
    
    if score > reject_threshold:
        logger.info("""Rejected comment with score of %s:""" % (score) + """ IP Address: "%(ip_address)s" Name: "%(user_name)s" Email: "%(user_email)s" URL: "%(user_url)s" Comment: "%(comment)s" """ % comment.__dict__)
        return False
    if score > getattr(settings, 'FCCV_PUBLIC_THRESHOLD', 0.1):
        logger.info("""Comment spam score is %s; marking it non-public.""" % score)
        comment.is_public = False
    return True

comment_will_be_posted.connect(validate_comment, sender=Comment)
