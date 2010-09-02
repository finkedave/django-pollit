import datetime
from django.db import models

from django.contrib.sites.models import Site
from django.contrib.auth.models import User
from django.db.models import permalink
from django.conf import settings
from django.http import Http404

POLL_STATUS = (
    (1, 'Controlled By Expire Date'),
    (2, 'Open'),
    (3, 'Closed')
)
POLL_COMMENT_STATUS = (
    (1, 'Disabled'),
    (2, 'Show Only'),
    (3, 'Enabled'),
    (4, 'Allowed'),
)

class AlreadyVoted(Exception):
    """
    The user has already voted
    """
    pass

class PollExpired(Exception):
    """
    The poll has expired
    """
    pass

class PollManager(models.Manager):
    def get_latest_polls(self, count=10):
        queryset = super(PollManager, self).get_query_set()
        polls = queryset.filter(
            sites__pk__in=[settings.SITE_ID,], 
            status__in=[1,2],
            pub_date__lt=datetime.datetime.now()).order_by('-pub_date')
            
        poll_list = []
        for poll in polls:
            if poll.status == 1 and poll.expire_date:
                if poll.expire_date > datetime.datetime.now():
                    poll_list.append(poll)
            elif poll.status == 2:
                poll_list.append(poll)
                
        return poll_list[:count]
    
    def update_total_votes(self):
        """
        Just in case the total_votes field in the Poll model isn't or wasn't
        getting updated properly, this function will recalculate it by summing
        the choice totals.
        """
        sql = """UPDATE pollit_poll SET total_votes = v.votes
            FROM (SELECT poll_id, SUM(votes) FROM pollit_pollchoice 
            GROUP BY poll_id) v WHERE pollit_poll.id = v.poll_id"""
        from django.db import connection, transaction
        cursor = connection.cursor()
        cursor.execute(sql)
        transaction.commit_unless_managed()


class Poll(models.Model):
    question = models.CharField(max_length=255)
    slug = models.SlugField()
    pub_date = models.DateTimeField(blank=True, null=True)
    types = models.ManyToManyField(PollType, null=True, blank=True, related_name="polls")
    sites = models.ForeignKey(Site, related_name="polls")
    status = models.PositiveIntegerField(default=2, choices=POLL_STATUS)
    expire_date = models.DateTimeField(blank=True, null=True)
    comment_status = models.IntegerField('Comments', 
        default=3, choices=POLL_COMMENT_STATUS)
    
    objects = PollManager()
    
    class Meta:
        ordering = ('-pub_date',)
    
    def __unicode__(self):
        return self.question
        
    def get_absolute_url(self):
        return ('pollit_detail', None, {
                'year': self.pub_date.strftime("%Y"),
                'month': self.pub_date.strftime("%b").lower(),
                'slug': self.slug })
    get_absolute_url = permalink(get_absolute_url)  
    
    def user_can_vote(self, user):
        try:
            PollChoiceData.objects.get(poll__pk=self.pk, user__pk=user.pk)
            return False
        except:
            return True
            
    def is_expired(self):
        if not self.pub_date:
            return True
        if not expire_date and status [1, 2]:
            return False
        if status == 3:
            return True
            
        if self.expire_date and self.expire_date <= datetime.datetime.now():
            return True
            
    def publish(self):
        self.pub_date = datetime.datetime.now()
        self.save()
        
        
class PollChoice(models.Model):
    poll = models.ForeignKey(Poll)
    choice = models.CharField(max_length=255)
    votes = models.IntegerField(editable=False, default=0)
    order = models.IntegerField(default=1)
    
    def percentage(self):
        if not self.votes:
            return 0
            
        total = PollChoice.objects.filter(poll=self.poll).aggregate(Sum('votes'))
        if total['votes__sum'] == 0:
            return 0
        return int((float(self.votes) / float(total['votes__sum'])) * 100)
    
    def __unicode__(self):
        return self.choice
        
    class Meta:
        ordering = ['order',]
        
        
class PollChoiceData(models.Model):
    choice = models.ForeignKey(PollChoice)
    user = models.ForeignKey(User)
    