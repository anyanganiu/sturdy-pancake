from django.db import models
from django.utils import timezone
from users.models import User


# Create your models here.
# 文章分类模型
class ArticleCategory(models.Model):
    """文章分类"""
    title = models.CharField(max_length=100, blank=True, verbose_name="文章标题")
    created = models.DateTimeField(default=timezone.now, verbose_name="文章创建时间")

    # admin站点显示，调试查看对象方便
    def __str__(self):
        return self.title

    class Meta:
        db_table = 'tb_category'  # 修改表名
        verbose_name = "类别管理"  # admin后台显示，超级管理员才能登录的Django管理后台
        verbose_name_plural = verbose_name


# 文章模型
class Article(models.Model):
    """文章模型"""
    author = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="文章作者")
    avatar = models.ImageField(verbose_name="标题图", upload_to="article/%Y%m%d/", blank=True)
    title = models.CharField(verbose_name="标题", max_length=100, blank=True)
    # 文章栏目的 “一对多” 外键
    category = models.ForeignKey(ArticleCategory, null=True, blank=True, on_delete=models.CASCADE,
                                 related_name='article', verbose_name="文章的类别")
    tags = models.CharField(verbose_name="标签", max_length=20, blank=True)
    summary = models.CharField(verbose_name="摘要信息", max_length=200, blank=False, null=False)
    content = models.TextField(verbose_name="文章正文")
    total_views = models.PositiveIntegerField(verbose_name="浏览量", default=0)
    comments_count = models.PositiveIntegerField(verbose_name="评论量", default=0)
    created = models.DateTimeField(verbose_name="文章创建时间", default=timezone.now)
    updated = models.DateTimeField(verbose_name="文章修改时间", auto_now=True)

    # 修改表名以及admin后台展示的配置信息等
    class Meta:
        db_table = 'tb_article'
        ordering = ('-created',)  # 排序
        verbose_name = "文章管理"
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.title


# 评论模型
class Comment(models.Model):
    """评论模型类"""
    content = models.TextField(verbose_name="评论内容")
    article = models.ForeignKey(Article, on_delete=models.SET_NULL, null=True, verbose_name="评论的文章")
    user = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, verbose_name="评论的用户")
    created = models.DateTimeField(verbose_name="评论时间", auto_now_add=True)

    def __str__(self):
        return self.article.title

    class Meta:
        db_table = 'tb_comment'
        verbose_name = "评论管理"
        verbose_name_plural = verbose_name
