"""
Project: META-SHARE 
Author: Christian Girardi <cgirardi@fbk.eu>
"""

from django.shortcuts import render_to_response     
from metashare.stats.models import LRStats, QueryStats
from metashare.stats.model_utils import getLRTop, getLastQuery, getLRLast, statDays, VIEW_STAT, UPDATE_STAT, DOWNLOAD_STAT
from django.db.models import Count, Max, Min, Avg
from django.http import HttpResponse
from json import JSONEncoder
from datetime import datetime, date
import urllib
import base64
try:
    import cPickle as pickle
except:
    import pickle

# pylint: disable-msg=W0611, W0401
from metashare.repo2.models import *

#possible models and their default field
SELECT_MODEL = {'Language': ['languageInfoType_model', 'languageName'],
                'Licence': ['licenceInfoType_model', 'licence'],
                'Creator': ['communicationInfoType_model','country'],
                'Organization': ['organizationInfoType_model','organizationName'],
                'Distribution': ['distributionInfoType_model', 'availability'],
                'Linguality': ['lingualityInfoType_model', 'lingualityType'],
                'Annotation': ['annotationInfoType_model', 'annotationFormat']}
#no accessable field
NOACCESS_FIELDS = ["downloadLocation", "executionLocation"]

# Setup logging support.
logging.basicConfig(level=LOG_LEVEL)
LOGGER = logging.getLogger('metashare.stats.views')
LOGGER.addHandler(LOG_HANDLER)

def repostats (request):    
    selected_menu_value = []
    modelname = request.POST.get('model', 'Language')
    selected_menu_value.append(['model', modelname])
    i = 0
    while():
        imodel = request.POST.get('model'+str(i))
        if (imodel != None):
            selected_menu_value.append(['model'+str(i), imodel])
        else:
            break
        i += 1
    # Get lists of languages, resource types and media types to show in filtering
    dbmodel = SELECT_MODEL[str(modelname)][0]
    dbfield = request.POST.get('field')        
    if (dbfield == None or dbfield == ""):
        dbfield = SELECT_MODEL[str(modelname)][1]
    selected_menu_value.append(['field', dbfield])
    
    dbfields = []
    dbclasses = eval(u'{0}.__schema_classes__'.format(dbmodel))
    relational_fields = []
    for field in eval(u'{0}.__schema_fields__'.format(dbmodel)):
        if field[0] in NOACCESS_FIELDS:
            continue  
        if (field[0] in dbclasses):
            relational_fields.append(field)
        else:
            if (isinstance(field[0], unicode)):
                dbfields.append(field)
        
    repodata = []
    if (dbfield != ""):
        if (dbfield in dbclasses):
            values = eval(u'{0}._meta.get_field("{1}").choices'.format(dbclasses[dbfield], dbfield))
        else:    
            values = eval(u'{0}._meta.get_field("{1}").choices'.format(dbmodel, dbfield))
        
        result = eval(u'{0}.objects.values("{1}").annotate(Count("{1}")).order_by("-{1}__count")'.format(dbmodel, dbfield))
        for item in result:
            value = item[dbfield]
            if (value != None and value != ""):
                if (isinstance(value, basestring)):
                    if (hasattr(value, 'encode')):
                        value = value.encode("utf-8")
                        print "VAL: " +str(value)
                    try:
                        value = pickle.loads(base64.b64decode(str(value)))              
                    except:
                        LOGGER.debug("Warning! Value of field {0} is not encoded base64: {1}".format(dbfield,value))
                                            
                if (isinstance(value, list)):
                    for val in value:      
                        repodata.append([val.encode("utf-8"), item[dbfield + "__count"]])
                else:
                    if (values != None and len(values) > 0):
                        repodata.append([str(values[int(value)][1]), item[dbfield + "__count"]])    
                    else:
                        repodata.append([str(value), item[dbfield + "__count"]])
                    
    return render_to_response('stats/repostats.html',
        {'result': repodata, 'selected_menu_value': selected_menu_value, 'models': SELECT_MODEL.keys(), 'fields': dbfields, "subfields": relational_fields})


def usagestats (request):
    # Get lists of fields used in the advanced search
    topdata = []
    result = QueryStats.objects.filter(query__contains=':').values("query").annotate(Count("query")).order_by('-query__count')
    if (len(result) == 0):
        result = QueryStats.objects.values("query").annotate(Count("query")).order_by('-query__count')
    for item in result:
        value = urllib.unquote(item["query"])
        topdata.append([value, item["query__count"]])       
         
    return render_to_response('stats/usagestats.html',
        {'result': topdata})

    
def topstats (request):
    """ viewing statistics about the top LR and latest queries. """
    topdata = []
    view = request.GET.get('view', 'topviewed')
    if view == "topviewed":
        data = getLRTop(VIEW_STAT, 10)
        for item in data:
            try:
                res_info =  resourceInfoType_model.objects.get(storage_object__identifier=item['lrid'])
                topdata.append([res_info.id, res_info.get_absolute_url, item['sum_count'], res_info])
            except: 
                LOGGER.debug("Warning! The object "+item['lrid']+ " has not been found.")
                
    if (view == "latestupdated"):
        data = getLRLast(UPDATE_STAT, 10)
        for item in data:
            try:
                res_info =  resourceInfoType_model.objects.get(storage_object__identifier=item['lrid'])
                topdata.append([res_info.id,  res_info.get_absolute_url, pretty_timeago(item['lasttime']), res_info])
            except: 
                LOGGER.debug("Warning! The object "+item['lrid']+ " has not been found.")
    if (view == "topdownloaded"):
        data = getLRTop(DOWNLOAD_STAT, 10)
        for item in data:
            try:
                res_info =  resourceInfoType_model.objects.get(storage_object__identifier=item['lrid'])
                topdata.append([res_info.id, res_info.get_absolute_url, item['sum_count'], res_info])
            except: 
                LOGGER.debug("Warning! The object "+item['lrid']+ " has not been found.")

    if view == "latestqueries":
        data = getLastQuery(10)
        for item in data:
            query = urllib.unquote(item['query'])
            topdata.append([query, pretty_timeago(item['lasttime']), item['found']])       
             
    return render_to_response('stats/topstats.html',
      {'topdata': topdata[:10], 'view': view})

def statdays (request):
    """ get dates where there are some statistics """
    dates = []
    for day in statDays():
        dates.append(day.strftime("%Y-%m-%d"))
    return HttpResponse(JSONEncoder().encode(dates))

def getstats (request):
    """ get statistics for a date in terms of user action made """
    currdate = request.GET.get('date',"")
    if (not currdate):
        currdate = date.today()
        
    user = LRStats.objects.filter(lasttime__startswith=currdate).values('sessid').annotate(Count('sessid')).count()
    ##optimize these calls just using one (model_utils.statByDate)
    lrupdate = LRStats.objects.filter(lasttime__contains=currdate, action="u").count()
    lrview = LRStats.objects.filter(lasttime__contains=currdate, action="v").count()
    lrdown = LRStats.objects.filter(lasttime__contains=currdate, action="d").count()
    queries = QueryStats.objects.filter(lasttime__contains=currdate).count()
    extimes = QueryStats.objects.filter(lasttime__contains=currdate).aggregate(Avg('exectime'), Max('exectime'), Min('exectime'))
    
    qltavg = 0
    if (extimes["exectime__avg"]):
        qltavg = QueryStats.objects.filter(lasttime__contains=currdate, exectime__lt = int(extimes["exectime__avg"])).count()
    else:
        extimes["exectime__avg"] = 0
        
    return HttpResponse("["+JSONEncoder().encode({"date": str(currdate), "user": user, "lrupdate": lrupdate, "lrview": lrview, "lrdown": lrdown, "queries": queries, "qexec_time_avg": extimes["exectime__avg"], "qlt_avg": qltavg})+"]")


def pretty_timeago(time=False):
    """
    Get a datetime object or a int() Epoch timestamp and return a
    pretty string like 'an hour ago', 'Yesterday', '3 months ago',
    'just now', etc
    """   
    now = datetime.now()
    if type(time) is int:
        diff = now - datetime.fromtimestamp(time)
    elif isinstance(time, datetime):
        diff = now - time 
    elif not time:
        diff = now - now
    second_diff = diff.seconds
    day_diff = diff.days

    if day_diff < 0:
        return ''

    if day_diff == 0:
        if second_diff < 10:
            return "just now"
        if second_diff < 60:
            return str(second_diff) + " seconds ago"
        if second_diff < 120:
            return  "a minute ago"
        if second_diff < 3600:
            return str( second_diff / 60 ) + " minutes ago"
        if second_diff < 7200:
            return "an hour ago"
        if second_diff < 86400:
            return str( second_diff / 3600 ) + " hours ago"
    if day_diff == 1:
        return "Yesterday"
    if day_diff < 7:
        return str(day_diff) + " days ago"
    if day_diff < 31:
        return str(day_diff/7) + " weeks ago"
    if day_diff < 365:
        return str(day_diff/30) + " months ago"
    return str(day_diff/365) + " years ago"
