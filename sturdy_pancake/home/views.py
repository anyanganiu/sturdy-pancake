from django.http import JsonResponse
from django.http.response import HttpResponseNotFound, HttpResponseBadRequest
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.views import View
from django.core.paginator import Paginator, EmptyPage

from home.models import ArticleCategory, Article, Comment

import logging

logger = logging.getLogger('django')


# 首页视图
# Create your views here.
class IndexView(View):
    def get(self, request):
        # 1获取所有分类信息
        categories = ArticleCategory.objects.all()
        # 2.接收用户点击的分类id
        cat_id = request.GET.get('cat_id', 1)
        # 3.根据分类id进行分类的查询
        try:
            category = ArticleCategory.objects.get(id=cat_id)
        except ArticleCategory.DoesNotExist:
            return HttpResponseNotFound("没有此分类")
        # 4.获取分页参数
        page_num = request.GET.get('page_num', 1)
        page_size = request.GET.get('page_size', 10)
        # 5.根据分类信息查询文章数据
        articles = Article.objects.filter(category=category)
        # 6.创建分页器
        paginator = Paginator(articles, per_page=page_size)
        # 7.进行分页处理
        try:
            page_articles = paginator.page(page_num)
        except EmptyPage:
            return HttpResponseNotFound("empty page")
        # 总页数
        total_page = paginator.num_pages
        # 8.组织数据传递给模板
        context = {
            'categories': categories,
            'category': category,
            'page_articles': page_articles,
            'page_size': page_size,
            'total_page': total_page,
            'page_num': page_num,
        }
        return render(request, "index.html", context=context)


# 博客详情视图
class DetailView(View):
    def get(self, request):
        # 1.接收文章id信息
        id = request.GET.get('id', 1)
        # 2.根据文章id进行文章数据的查询
        try:
            article = Article.objects.get(id=id)
        except Article.DoesNotExist:
            return render(request, "404.html")
        else:
            # 让浏览量+1
            article.total_views += 1
            article.save()
        # 3.查询分类数据
        categories = ArticleCategory.objects.all()
        # 查询浏览量前10的文章数据
        hot_articles = Article.objects.order_by('-total_views')[:10]
        # 4.获取分页请求参数
        page_size = request.GET.get('page_size', 10)
        page_num = request.GET.get('page_num', 1)
        # 5.根据文章信息查询评论数据
        comments = Comment.objects.filter(article=article).order_by('-created')
        # 获取评论总数
        total_count = comments.count()
        # 6.创建分页器
        paginator = Paginator(comments, per_page=page_size)
        # 7.分页处理
        try:
            page_comments = paginator.page(page_num)
        except EmptyPage:
            return HttpResponseNotFound("empty page")
        # 总页数
        total_page = paginator.num_pages
        # 8.组织模板数据
        context = {
            'article': article,  # 文章信息
            'categories': categories,  # 所有的分类信息
            'category': article.category,  # 当前的分类
            'hot_articles': hot_articles,  # 浏览量前10的文章推荐
            'total_count': total_count,  # 总评论数
            'comments': comments,  # 所有的评论数据
            'page_size': page_size,  # 每页多少条数据
            'total_page': total_page,  # 总页数
            'page_num': page_num,  # 当前是第几页数据
        }
        return render(request, "detail.html", context=context)

    def post(self, request):
        # 1.接收用户信息
        user = request.user
        # 2.判断用户是否登录
        # 3.登录用户则可以接收form数据
        if user and user.is_authenticated:
            #   3.1接收评论数据
            id = request.POST.get('id', 1)
            content = request.POST.get('content')
            #   3.2验证文章是否存在
            try:
                article = Article.objects.get(id=id)
            except Article.DoesNotExist:
                return HttpResponseNotFound("没有此文章")
            #   3.3保存评论数据
            Comment.objects.create(
                content=content,
                article=article,
                user=user,
            )
            #   3.4修改文章评论数量
            article.comments_count += 1
            article.save()
            # 刷新当前页面（页面重定向）
            path = reverse('home:detail') + '?id={}'.format(article.id)
            return redirect(path)
        # 4.未登录用户则跳转到登录页面
        else:
            return redirect(reverse("users:login"))


# 博客修改视图
class EditView(View):
    def get(self, request):
        # 1.接收文章id信息
        id = request.GET.get('id', 1)
        # 2.根据文章id进行文章数据的查询
        try:
            article = Article.objects.get(id=id)
        except Article.DoesNotExist:
            return render(request, "404.html")
        # 3.查询所有的分类数据
        categories = ArticleCategory.objects.all()
        # 判断用户是否登录，登录则可以修改，未登录要进行登录
        user = request.user
        if user and user.is_authenticated:
            context = {
                'article': article,
                'categories': categories,
            }
            return render(request, "edit_blog.html", context=context)
        else:
            return redirect(reverse("users:login"))

    def post(self, request):
        # 1.接收编辑后的数据
        id = request.GET.get('id', 1)
        # 2.验证文章是否存在
        try:
            article = Article.objects.get(id=id)
        except Article.DoesNotExist:
            return HttpResponseNotFound("没有此文章")
        avatar = request.FILES.get('avatar', article.avatar)
        title = request.POST.get('title')
        category_id = request.POST.get('category')
        tags = request.POST.get('tags')
        summary = request.POST.get('summary')
        content = request.POST.get('content')
        # 3.判断分类id
        try:
            category = ArticleCategory.objects.get(id=category_id)
        except ArticleCategory.DoesNotExist:
            return HttpResponseBadRequest("没有此分类")
        # 4.保存编辑后的博客数据
        try:
            article.avatar = avatar
            article.title = title
            article.category = category
            article.tags = tags
            article.summary = summary
            article.content = content
            article.save()
        except Exception as e:
            logger.error(e)
            return HttpResponseNotFound("修改失败，请稍后重试！")
        # 5.刷新当前页面（页面重定向）
        path = reverse('home:detail') + '?id={}'.format(article.id)
        return redirect(path)


# 博客删除视图
class DeleteView(View):
    def get(self, request, nid):
        # 1.接收文章id信息
        id = request.GET.get('nid', 1)
        # 2.根据文章id进行文章数据的查询
        try:
            article = Article.objects.get(id=id)
        except Article.DoesNotExist:
            return render(request, "404.html")

        # article = get_object_or_404(Article, pk=nid)    # 代替了上面的抛出异常

        user = request.user
        if user and user.is_authenticated:
            Article.objects.filter(id=nid).delete()
            # return render(request, "index.html")
            return redirect(reverse("home:index"))
        else:
            return redirect(reverse("users:login"))
