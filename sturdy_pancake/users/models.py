from django.db import models
from django.contrib.auth.models import AbstractUser


# Create your models here.
class User(AbstractUser):
    # 手机号，必传的，blank=False
    mobile = models.CharField(max_length=11, unique=True, blank=False)
    # 头像信息，不是必传的，blank=True
    avatar = models.ImageField(upload_to='avatar/%Y%m%d/', blank=True)
    # 简介信息
    user_desc = models.TextField(max_length=500, blank=True)

    # 修改默认的认证字段为手机号，默认是对username进行认证。我们需要修改认证的字段为mobile。所以我们需要在User的模型中修改
    USERNAME_FIELD = 'mobile'

    # 注册/新增超级管理员必须输入的字段（不包括手机号和密码）
    REQUIRED_FIELDS = ['username', 'email']

    class Meta:
        db_table = 'tb_users'      # 修改表名
        verbose_name = '用户管理'       # admin后台显示
        verbose_name_plural = verbose_name    # admin后台显示

    def __str__(self):
        return self.mobile
