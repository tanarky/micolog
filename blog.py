# coding: utf-8
import cgi, os
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
from google.appengine.dist import use_library
use_library('django', '1.2')
import wsgiref.handlers

# Google App Engine imports.
##import app.webapp as webapp2

from datetime import timedelta
import random
from django.utils import simplejson
import app.filter as myfilter
from app.safecode import Image
from app.gmemsess import Session
from base import *
from model import *
from django.utils.translation import ugettext as _

from google.appengine.api import memcache

def doRequestHandle(old_handler,new_handler,**args):
    new_handler.initialize(old_handler.request,old_handler.response)
    return  new_handler.get(**args)

def doRequestPostHandle(old_handler,new_handler,**args):
    new_handler.initialize(old_handler.request,old_handler.response)
    return  new_handler.post(**args)

class BasePublicPage(BaseRequestHandler):
    def initialize(self, request, response):
        BaseRequestHandler.initialize(self,request, response)
    def get_sidebar(self):
        sidebar = memcache.get('sidebar')
        if not sidebar:
            logging.info('cache miss')
            sidebar = self.get_render('sidebar', dict(categories=Category.allTops()))
            memcache.set('sidebar', sidebar, 60*60*24)
        return sidebar

class MainPage(BasePublicPage):
    def head(self,page=1):
        if g_blog.allow_pingback :
            self.response.headers['X-Pingback']="%s/rpc"%str(g_blog.baseurl)
            
    def get(self,page=1):
        postid=self.param('p')
        if postid:
            try:
                postid=int(postid)
                return doRequestHandle(self,SinglePost(),postid=postid)  #singlepost.get(postid=postid)
            except:
                return self.error(404)
        if g_blog.allow_pingback :
            self.response.headers['X-Pingback']="%s/rpc"%str(g_blog.baseurl)

        self.doget(page)

    def post(self):
        postid=self.param('p')
        if postid:
            try:
                postid=int(postid)
                return doRequestPostHandle(self,SinglePost(),postid=postid)  #singlepost.get(postid=postid)
            except:
                return self.error(404)


    @cache()
    def doget(self,page):
        page=int(page)

        entrycount=g_blog.postscount()
        max_page = entrycount / g_blog.posts_per_page + ( entrycount % g_blog.posts_per_page and 1 or 0 )

        if page < 1 or page > max_page:
                return	self.error(404)

        entries = Entry.all().filter('entrytype =','post').\
                filter("published =", True).order('-sticky').order('-date').\
                fetch(self.blog.posts_per_page, offset = (page-1) * self.blog.posts_per_page)

        show_prev = entries and  (not (page == 1))
        show_next = entries and  (not (page == max_page))
        #print page,max_page,g_blog.entrycount,self.blog.posts_per_page

        return self.render('index',
                           dict(entries=entries,
                                sidebar=self.get_sidebar(),
                                show_prev=show_prev,
                                show_next=show_next,
                                pageindex=page,
                                ishome=True,
                                pagecount=max_page,
                                postscounts=entrycount))

class entriesByCategory(BasePublicPage):
    @cache()
    def get(self,slug=None):

        if not slug:
            self.error(404)
            return

        try:
            page_index=int(self.param('page'))
        except:
            page_index=1

        slug=urldecode(slug)

        cats=Category.all().filter('slug =',slug).fetch(1)
        if cats:
            entries=Entry.all().filter("published =", True).filter('categorie_keys =',cats[0].key()).order("-date")
            entries,links=Pager(query=entries,items_per_page=20).fetch(page_index)
            self.render('category', {'entries':entries, 'category':cats[0], 'pager':links, 'sidebar':self.get_sidebar()})
        else:
            self.error(404,slug)

class archiveByMonth(BasePublicPage):
    @cache()
    def get(self,year,month):
        try:
            page_index=int (self.param('page'))
        except:
            page_index=1

        firstday=datetime(int(year),int(month),1)
        if int(month)!=12:
            lastday=datetime(int(year),int(month)+1,1)
        else:
            lastday=datetime(int(year)+1,1,1)
        entries=db.GqlQuery("SELECT * FROM Entry WHERE date > :1 AND date <:2 AND entrytype =:3 AND published = True ORDER BY date DESC",firstday,lastday,'post')
        entries,links=Pager(query=entries).fetch(page_index)

        self.render('month', {'entries':entries,
                              'year':year,
                              'month':month,
                              'pager':links,
                              'sidebar':self.get_sidebar()})

class entriesByTag(BasePublicPage):
    @cache()
    def get(self,slug=None):
        if not slug:
             self.error(404)
             return

        try:
            page_index=int (self.param('page'))
        except:
            page_index=1
        slug=urldecode(slug)

        tags = slug.split(" ")
        entries=Entry.all().filter("published =", True)
        for t in tags:
            entries = entries.filter('tags =', t)
        entries = entries.order("-date")

        entries,links=Pager(query=entries,items_per_page=20).fetch(page_index)
        self.render('tag',{'entries':entries,'tag':slug,'pager':links, 'sidebar':self.get_sidebar()})

class SinglePost(BasePublicPage):
    def paramint(self, name, default=0):
        try:
           return int(self.request.get(name))
        except:
           return default

    def head(self,slug=None,postid=None):
        if g_blog.allow_pingback :
            self.response.headers['X-Pingback']="%s/rpc"%str(g_blog.baseurl)

    @cache()
    def get(self,slug=None,postid=None):
        #logging.error('postid = %s, slug = %s' % (postid, slug))

        if postid:
            entries = Entry.all().filter("published =", True).filter('post_id =', postid).fetch(1)
        else:
            slug=urldecode(slug)
            entries = Entry.all().filter("published =", True).filter('link =', slug).fetch(1)
        if not entries or len(entries) == 0:
            return self.error(404)

        mp=self.paramint("mp",1)

        entry=entries[0]
        if entry.is_external_page:
            return self.redirect(entry.external_page_address,True)
        if g_blog.allow_pingback and entry.allow_trackback:
            self.response.headers['X-Pingback']="%s/rpc"%str(g_blog.baseurl)
        #entry.readtimes += 1
        #entry.put()
        self.entry   = entry

        comments     = entry.get_comments_by_page(mp,self.blog.comments_per_page)
        commentuser  = ['','','']
        comments_nav = self.get_comments_nav(mp,entry.purecomments().count())

        if entry.entrytype=='post':
            self.render('single',
                        dict(entry=entry,
                             sidebar=self.get_sidebar(),
                             relateposts=entry.relateposts,
                             comments=comments,
                             user_name=commentuser[0],
                             user_email=commentuser[1],
                             user_url=commentuser[2],
                             checknum1=random.randint(1, 10),
                             checknum2=random.randint(1, 10),
                             comments_nav=comments_nav))

        else:
            self.render('page',
                        dict(entry=entry, relateposts=entry.relateposts, comments=comments, user_name=commentuser[0],
                             user_email=commentuser[1], user_url=commentuser[2], checknum1=random.randint(1, 10),
                             checknum2=random.randint(1, 10), comments_nav=comments_nav))

    def post(self,slug=None,postid=None):
        '''handle trackback'''
        error = '''<?xml version="1.0" encoding="utf-8"?>
<response>
<error>1</error>
<message>%s</message>
</response>
'''
        success = '''<?xml version="1.0" encoding="utf-8"?>
<response>
<error>0</error>
</response>
'''

        if not g_blog.allow_trackback:
            self.response.out.write(error % "Trackback denied.")
            return
        self.response.headers['Content-Type'] = "text/xml"
        if postid:
            entries = Entry.all().filter("published =", True).filter('post_id =', postid).fetch(1)
        else:
            slug=urldecode(slug)
            entries = Entry.all().filter("published =", True).filter('link =', slug).fetch(1)

        if not entries or len(entries) == 0 :#or  (postid and not entries[0].link.endswith(g_blog.default_link_format%{'post_id':postid})):
            self.response.out.write(error % "empty slug/postid")
            return
        #check code ,rejest spam
        entry=entries[0]
        #logging.info(self.request.remote_addr+self.request.path+" "+entry.trackbackurl)
        #key=self.param("code")
        #if (self.request.uri!=entry.trackbackurl) or entry.is_external_page or not entry.allow_trackback:
        #import cgi
        from urlparse import urlparse
        param=urlparse(self.request.uri)
        code=param[4]
        param=cgi.parse_qs(code)
        if param.has_key('code'):
            code=param['code'][0]

        if  (not str(entry.key())==code) or entry.is_external_page or not entry.allow_trackback:
            self.response.out.write(error % "Invalid trackback url.")
            return


        coming_url = self.param('url')
        blog_name = myfilter.do_filter(self.param('blog_name'))
        excerpt = myfilter.do_filter(self.param('excerpt'))
        title = myfilter.do_filter(self.param('title'))

        if not coming_url or not blog_name or not excerpt or not title:
            self.response.out.write(error % "not enough post info")
            return

        import time
        #wait for half second in case otherside hasn't been published
        time.sleep(0.5)

##		#also checking the coming url is valid and contains our link
##		#this is not standard trackback behavior
##		try:
##
##			result = urlfetch.fetch(coming_url)
##			if result.status_code != 200 :
##				#or ((g_blog.baseurl + '/' + slug) not in result.content.decode('ascii','ignore')):
##				self.response.out.write(error % "probably spam")
##				return
##		except Exception, e:
##			logging.info("urlfetch error")
##			self.response.out.write(error % "urlfetch error")
##			return

        comment = Comment.all().filter("entry =", entry).filter("weburl =", coming_url).get()
        if comment:
            self.response.out.write(error % "has pinged before")
            return

        comment=Comment(author=blog_name,
                content="...<strong>"+title[:250]+"</strong> " +
                        excerpt[:250] + '...',
                weburl=coming_url,
                entry=entry)

        comment.ip=self.request.remote_addr
        comment.ctype=COMMENT_TRACKBACK
        try:
            comment.save()

            memcache.delete("/"+entry.link)
            self.write(success)
            g_blog.tigger_action("pingback_post",comment)
        except:
            self.response.out.write(error % "unknow error")

    def get_comments_nav(self,pindex,count):
        maxpage=count / g_blog.comments_per_page + ( count % g_blog.comments_per_page and 1 or 0 )
        if maxpage==1:
            return {'nav':"",'current':pindex}

        result=""

        if pindex>1:
            result="<a class='comment_prev' href='"+self.get_comments_pagenum_link(pindex-1)+"'>«</a>"

        minr=max(pindex-3,1)
        maxr=min(pindex+3,maxpage)
        if minr>2:
            result+="<a class='comment_num' href='"+self.get_comments_pagenum_link(1)+"'>1</a>"
            result+="<span class='comment_dot' >...</span>"

        for n in range(minr,maxr+1):
            if n==pindex:
                result+="<span class='comment_current'>"+str(n)+"</span>"
            else:
                result+="<a class='comment_num' href='"+self.get_comments_pagenum_link(n)+"'>"+str(n)+"</a>"
        if maxr<maxpage-1:
            result+="<span class='comment_dot' >...</span>"
            result+="<a class='comment_num' href='"+self.get_comments_pagenum_link(maxpage)+"'>"+str(maxpage)+"</a>"

        if pindex<maxpage:
            result+="<a class='comment_next' href='"+self.get_comments_pagenum_link(pindex+1)+"'>»</a>"

        return {'nav':result,'current':pindex,'maxpage':maxpage}

    def get_comments_pagenum_link(self,pindex):
        url=str(self.entry.link)
        if url.find('?')>=0:
            return "/"+url+"&mp="+str(pindex)+"#comments"
        else:
            return "/"+url+"?mp="+str(pindex)+"#comments"

class SinglePost2(SinglePost):
    def head(self, postid=None, attr=None):
        return super(SinglePost2, self).head(slug=None, postid=int(postid))

    @cache()
    def get(self, postid=None, attr=None):
        if not attr or attr == "" or not attr.startswith("/"):
            return self.redirect("/?p=%s" % postid)
        return super(SinglePost2, self).get(slug=None, postid=int(postid))

    def post(self, postid=None, attr=None):
        return super(SinglePost2, self).post(slug=None, postid=int(postid))


class SinglePage(SinglePost):
    def head(self, slug=None):
        return super(SinglePage, self).head(slug=slug, postid=None)

    @cache()
    def get(self, slug=None):
        return super(SinglePage, self).get(slug=slug, postid=None)

    def post(self, slug=None):
        return super(SinglePage, self).post(slug=slug, postid=None)


class FeedHandler(BaseRequestHandler):
    @cache()
    def get(self,tags=None):
        if g_blog.timedelta < 0:
            sign = '-'
            delta = -1 * int(g_blog.timedelta)
        else:
            sign  = '+'
            delta = int(g_blog.timedelta)
        tz = '%s%04d' % (sign, (delta * 100))
        entries = Entry.all().filter('entrytype =','post').filter('published =',True).order('-date').fetch(10)
        if entries and entries[0]:
            last_updated = entries[0].date
            last_updated = last_updated.strftime("%s %s" % ("%a, %d %b %Y %H:%M:%S", tz))
        for e in entries:
            #e.formatted_date = e.date.strftime("%a, %d %b %Y %H:%M:%S +0000")
            e.formatted_date = e.date.strftime("%s %s" % ("%a, %d %b %Y %H:%M:%S", tz))
        self.response.headers['Content-Type'] = 'application/rss+xml; charset=utf-8'
        self.render2('views/rss.xml',{'entries':entries,'last_updated':last_updated})

class CommentsFeedHandler(BaseRequestHandler):
    @cache()
    def get(self,tags=None):
        comments = Comment.all().order('-date').filter('ctype =',0).fetch(10)
        if comments and comments[0]:
            last_updated = comments[0].date
            last_updated = last_updated.strftime("%a, %d %b %Y %H:%M:%S +0000")
        for e in comments:
            e.formatted_date = e.date.strftime("%a, %d %b %Y %H:%M:%S +0000")
        self.response.headers['Content-Type'] = 'application/rss+xml; charset=UTF-8'
        self.render2('views/comments.xml',{'comments':comments,'last_updated':last_updated})

class SitemapHandler(BaseRequestHandler):
    @cache(time=86400)
    def get(self,tags=None):
        urls = []
        def addurl(loc,lastmod=None,changefreq=None,priority=None):
            url_info = {
                'location':   loc,
                'lastmod':    lastmod,
                'changefreq': changefreq,
                'priority':   priority
            }
            urls.append(url_info)

        addurl(g_blog.baseurl,changefreq='daily',priority=0.9 )

        entries = Entry.all().filter('published =',True).order('-date').fetch(g_blog.sitemap_entries)

        for item in entries:
            loc = "%s/%s" % (g_blog.baseurl, item.link)
            addurl(loc,item.mod_date or item.date,'never',0.6)

        if g_blog.sitemap_include_category:
            cats=Category.all()
            for cat in cats:
                loc="%s/category/%s"%(g_blog.baseurl,cat.slug)
                addurl(loc,None,'weekly',0.5)

        if g_blog.sitemap_include_tag:
            tags=Tag.all()
            for tag in tags:
                loc="%s/tag/%s"%(g_blog.baseurl, urlencode(tag.tag))
                addurl(loc,None,'weekly',0.5)


	self.response.headers['Content-Type'] = 'application/xml; charset=UTF-8'
        self.render2('views/sitemap.xml',{'urlset':urls})


class Error404(BaseRequestHandler):
   @cache()
   def get(self,slug=None):
       self.error(404)

class PostComment(BaseRequestHandler):
    #@printinfo
    def post(self,slug=None):
        useajax=self.param('useajax')=='1'

        name=self.param('author')
        email=self.param('email')
        url=self.param('url')

        key=self.param('key')
        content=self.param('comment')
        parent_id=self.paramint('parentid',0)
        reply_notify_mail=self.parambool('reply_notify_mail')

        sess=Session(self,timeout=180)

        # ログインにかかわらず常にチェック
        #if not self.is_login:
        if True:
            #if not (self.request.cookies.get('comment_user', '')):
            try:
                check_ret=True
                if g_blog.comment_check_type in (1,2)  :
                    checkret=self.param('checkret')
                    check_ret=(int(checkret) == sess['code'])
                elif  g_blog.comment_check_type ==3:
                    import app.gbtools as gb
                    checknum=self.param('checknum')
                    checkret=self.param('checkret')
                    check_ret=eval(checknum)==int(gb.stringQ2B( checkret))

                if not check_ret:
                    if useajax:
                        self.write(simplejson.dumps((False,-102,_('Your check code is invalid .')),ensure_ascii = False))
                    else:
                        self.error(-102,_('Your check code is invalid .'))
                    return
            except:
                if useajax:
                    self.write(simplejson.dumps((False,-102,_('Your check code is invalid .')),ensure_ascii = False))
                else:
                    self.error(-102,_('Your check code is invalid .'))
                return

        sess.invalidate()
        content=content.replace('\n','<br />')
        content=myfilter.do_filter(content)
        name=cgi.escape(name)[:20]
        url=cgi.escape(url)[:100]

        if not (name and email and content):
            if useajax:
                        self.write(simplejson.dumps((False,-101,_('Please input name, email and comment .'))))
            else:
                self.error(-101,_('Please input name, email and comment .'))
        else:
            comment=Comment(author=name,
                            content=content,
                            email=email,
                            reply_notify_mail=reply_notify_mail,
                            entry=Entry.get(key))
            if url:
                try:
                    if not url.lower().startswith(('http://','https://')):
                        url = 'http://' + url
                    comment.weburl=url
                except:
                    comment.weburl=None

            #name=name.decode('utf8').encode('gb2312')

            info_str='#@#'.join([urlencode(name),urlencode(email),urlencode(url)])

             #info_str='#@#'.join([name,email,url.encode('utf8')])
            cookiestr='comment_user=%s;expires=%s;path=/;'%( info_str,
                       (datetime.now()+timedelta(days=100)).strftime("%a, %d-%b-%Y %H:%M:%S GMT")
                       )
            comment.ip=self.request.remote_addr

            if parent_id:
                comment.parent=Comment.get_by_id(parent_id)

            comment.no=comment.entry.commentcount+1
            try:
                comment.save()
                memcache.delete("/"+comment.entry.link)

                self.response.headers.add_header( 'Set-Cookie', cookiestr)
                if useajax:
                    comment_c=self.get_render('comment',{'comment':comment})
                    self.write(simplejson.dumps((True,comment_c.decode('utf8')),ensure_ascii = False))
                else:
                    self.redirect(self.referer+"#comment-"+str(comment.key().id()))

                comment.entry.removecache()
                memcache.delete("/feed/comments")
            except:
                if useajax:
                    self.write(simplejson.dumps((False,-102,_('Comment not allowed.'))))
                else:
                    self.error(-102,_('Comment not allowed .'))

class ChangeTheme(BaseRequestHandler):
    @requires_admin
    def get(self,slug=None):
       theme=self.param('t')
       g_blog.theme_name=theme
       g_blog.get_theme()
       self.redirect('/')


class doAction(BaseRequestHandler):
    def get(self,slug=None):
        try:
            func=getattr(self,'action_'+slug)
            if func and callable(func):
                func()
            else:
                self.error(404)
        except BaseException,e:
            self.error(404)

    def post(self,slug=None):
        try:
            func=getattr(self,'action_'+slug)
            if func and callable(func):
                func()
            else:
                self.error(404)
        except:
             self.error(404)

    @ajaxonly
    def action_info_login(self):
        if self.login_user:
            self.write(simplejson.dumps({'islogin':True,
                                         'isadmin':self.is_admin,
                                         'name': self.login_user.nickname()}))
        else:
            self.write(simplejson.dumps({'islogin':False}))

    #@hostonly
    @cache()
    def action_proxy(self):
        result=urlfetch.fetch(self.param("url"), headers=self.request.headers)
        if result.status_code == 200:
            self.response.headers['Expires'] = 'Thu, 15 Apr 3010 20:00:00 GMT'
            self.response.headers['Cache-Control'] = 'max-age=3600,public'
            self.response.headers['Content-Type'] = result.headers['Content-Type']
            self.response.out.write(result.content)
        return

    def action_getcomments(self):
        key=self.param('key')
        entry=Entry.get(key)
        comments=Comment.all().filter("entry =",key)

        commentuser=self.request.cookies.get('comment_user', '')
        if commentuser:
            commentuser=commentuser.split('#@#')
        else:
            commentuser=['','','']


        vals= dict(entry=entry, comments=comments, user_name=commentuser[0], user_email=commentuser[1],
                   user_url=commentuser[2], checknum1=random.randint(1, 10), checknum2=random.randint(1, 10))
        html=self.get_render('comments',vals)

        self.write(simplejson.dumps(html.decode('utf8')))

    def action_test(self):
        self.write(settings.LANGUAGE_CODE)
        self.write(_("this is a test"))

class CheckImg(BaseRequestHandler):
    def get(self):
        img = Image()
        imgdata = img.create()
        sess=Session(self,timeout=900)
        if not sess.is_new():
            sess.invalidate()
            sess=Session(self,timeout=900)
        sess['code']=img.text
        sess.save()
        self.response.headers['Content-Type'] = "image/png"
        self.response.out.write(imgdata)

#class getMedia(webapp.RequestHandler):
#    def get(self,slug):
#        media=Media.get(slug)
#        if media:
#            self.response.headers['Expires'] = 'Thu, 15 Apr 3010 20:00:00 GMT'
#            self.response.headers['Cache-Control'] = 'max-age=3600,public'
#            self.response.headers['Content-Type'] = str(media.mtype)
#            self.response.out.write(media.bits)
#            a=self.request.get('a')
#            if a and a.lower()=='download':
#                media.download+=1
#                media.put()
#
#class CheckCode(BaseRequestHandler):
#    def get(self):
#        sess=Session(self,timeout=900)
#        num1=random.randint(30,50)
#        num2=random.randint(1,10)
#        code="<span style='font-size:12px;color:red'>%d - %d =</span>"%(num1,num2)
#        sess['code']=num1-num2
#        sess.save()
#        #self.response.headers['Content-Type'] = "text/html"
#        self.response.out.write(code)
#
#class Other(BaseRequestHandler):
#    def get(self,slug=None):
#        if not g_blog.tigger_urlmap(slug,page=self):
#            self.error(404)
#
#    def post(self,slug=None):
#        content=g_blog.tigger_urlmap(slug,page=self)
#        if content:
#            self.write(content)
#        else:
#            self.error(404)
#
#def getZipHandler(**args):
#    return ('/xheditor/(.*)',zipserve.make_zip_handler('''D:\\Projects\\eric-guo\\plugins\\xheditor\\xheditor.zip'''))

def main():
    webapp.template.register_template_library('app.filter')
    webapp.template.register_template_library('app.recurse')
    urls = [
            ('/\d{4}/\d{1,2}/(\d+)(.*)', SinglePost2),   # /2012/10/ID/SLUG
            ('/custom/(.*)',             SinglePage),    # /custom/SLUG
            ('/page/(.*)',               MainPage),      # /page/SLUG
            ('/tag/(.*)',                entriesByTag),
            ('/category/(.*)',           entriesByCategory),
            ('/(\d{4})/(\d{1,2})',       archiveByMonth),
            ('/',                        MainPage),
            ('/checkimg/',               CheckImg),
            ('/skin',                    ChangeTheme),
            ('/feed',                    FeedHandler),
            ('/feed/comments',           CommentsFeedHandler),
            ('/sitemap\.xml',            SitemapHandler),
            ('/post_comment',            PostComment),
            ('/do/(\w+)',                doAction),
            ('.*',Error404),

            ## 削除
            #('/checkcode/',              CheckCode),
            #('/media/([^/]*)/{0,1}.*',   getMedia),
            #('/sitemap',                 SitemapHandler),
            #('/e/(.*)',                  Other),
            #('/([\\w\\-\\./%]+)',        SinglePost),  # SinglePost2があれば要らない気がする
            ]
    
    application = webapp.WSGIApplication(urls)
    g_blog.application = application
    g_blog.plugins.register_handlerlist(application)
    wsgiref.handlers.CGIHandler().run(application)

if __name__ == "__main__":
    main()

