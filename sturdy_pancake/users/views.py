import re
from urllib import request

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views import View
from django.http.response import HttpResponseBadRequest, JsonResponse
from django_redis import get_redis_connection
from django.http import HttpResponse
from random import randint
from django.contrib.auth import login, authenticate, logout
from django.db import DatabaseError

from libs.captcha.captcha import captcha
from libs.yuntongxun.sms import CCP
from utils.response_code import RETCODE
from users.models import User
from home.models import ArticleCategory, Article

import logging

logger = logging.getLogger('django')


# Create your views here.
# 注册视图
class RegisterView(View):
    def get(self, request):
        return render(request, 'register.html')

    def post(self, request):
        """
        :param request:
        :return:
        """
        # 1.接收数据
        mobile = request.POST.get('mobile')
        password = request.POST.get('password')
        password2 = request.POST.get('password2')
        smscode = request.POST.get('sms_code')
        # 2.验证数据
        #   2.1验证参数是否齐全
        if not all([mobile, password, password2, smscode]):
            return HttpResponseBadRequest("缺少必要的参数")
        #   2.2手机号的格式是否正确
        if not re.match(r'^1[3-9]\d{9}$', mobile):
            return HttpResponseBadRequest("手机号不符合规则")
        #   2.3密码是否符合格式
        if not re.match(r'^[0-9A-Za-z]{8,20}$', password):
            return HttpResponseBadRequest("请输入8-20的密码，密码是数字、字母")
        #   2.4密码和确认密码是否一致
        if password != password2:
            return HttpResponseBadRequest("两次密码不一致")
        #   2.5短信验证码是否和redis中的一致
        redis_conn = get_redis_connection('default')
        redis_sms_code = redis_conn.get('sms:%s' % mobile)
        if redis_sms_code is None:
            return HttpResponseBadRequest("短信验证码已过期")
        if smscode != redis_sms_code.decode():
            return HttpResponseBadRequest("短信验证码有误")
        # 3.保存注册信息,create_user可以使用系统的方法来对密码进行加密
        try:
            user = User.objects.create_user(username=mobile, mobile=mobile, password=password)
        except DatabaseError as e:
            logger.error(e)
            return HttpResponseBadRequest("注册失败")
        login(request, user)
        # 4.返回响应跳转到指定页面，redirect是进行重定向，reverse是通过namespace:name来获取到视图所对应的路由
        response = redirect(reverse('home:index'))

        # 设置cookie信息，以方便首页中用户信息展示的判断和用户信息的展示
        response.set_cookie('is_login', True)  # 用户信息判断
        response.set_cookie('username', user.username, max_age=7 * 24 * 3600)  # 用户信息展示
        return response


# 验证码视图
class ImageCodeView(View):
    def get(self, request):
        """
        :param request:
        :return:
        """
        # 1.接收前端传递过来的uuid
        uuid = request.GET.get('uuid')
        # 2.判断uuid是否获取到
        if uuid is None:
            return HttpResponseBadRequest("没有传递uuid")
        # 3.通过调用captcha来生成图片验证码（图片内容和图片二进制）
        text, image = captcha.generate_captcha()
        # 4.将图片内容保存到redis中
        #   uuid作为一个key，图片内容作为一个value，同时我们还需要设置一个时效
        redis_conn = get_redis_connection('default')
        # redis_cli = get_redis_connection('code')
        # 第一个 key 设置为 uuid ，'img:%s' 为uuid的前缀
        # 第二个 seconds 过期秒数  为300秒，五分钟过期时间
        # 第三个 value 设置为 text
        redis_conn.setex('img:%s' % uuid, 300, text)
        # redis_cli.setex('img:%s' % uuid, 300, text)
        # 5. 返回图片二进制给前端，因为图片是二进制，不能返回json数据
        return HttpResponse(image, content_type='image/jpeg')


# 短信验证码视图
class SmsCodeView(View):
    """
    :param request:
    :return:
    """

    def get(self, request):
        # 1.接收参数（查询字符串形式传递过来）
        mobile = request.GET.get('mobile')
        image_code = request.GET.get('image_code')
        uuid = request.GET.get('uuid')
        # 2.参数验证
        #   2.1验证参数是否齐全
        if not all([mobile, image_code, uuid]):
            return JsonResponse({'code': RETCODE.NECESSARYPARAMERR, 'errmsg': "缺少必要的参数"})
        #   2.2图片验证码的验证
        #      连接redis获取redis中的图片验证码
        redis_conn = get_redis_connection('default')
        redis_image_code = redis_conn.get('img:%s' % uuid)
        #      判断图片验证码是否存在或是否过期
        if redis_image_code is None:
            return JsonResponse({'code': RETCODE.IMAGECODEERR, 'errmsg': "图片验证码已过期"})
        #      如果图片验证码未过期，获取到之后就可以删除图片验证码，让其不保存在库中
        try:
            redis_conn.delete('img:%s' % uuid)
        except Exception as e:
            logger.error(e)
        #      比对图片验证码，注意大小写的问题，redis的数据是bytes类型，redis里面的验证码要进行decode操作
        if redis_image_code.decode().lower() != image_code.lower():
            return JsonResponse({'code': RETCODE.IMAGECODEERR, 'errmsg': "图片验证码错误"})
        # 3.生成短信验证码
        sms_code = '%06d' % randint(0, 999999)
        # 为了后期比对方便，可以将短信验证码记录到日志中
        logger.info(sms_code)
        # 4.保存短信验证码到redis中
        redis_conn.setex('sms:%s' % mobile, 300, sms_code)
        # 5.发送短信
        # 注意： 测试的短信模板编号为1
        # 参数1：测试手机号
        # 参数2：列表（），您的验证码是{1}，请于{2}分钟内正确输入
        #               {1}：短信验证码
        #               {2}：短信有效期
        # 参数3：免费开发测试使用的模板ID为1
        CCP().send_template_sms(mobile, [sms_code, 5], 1)
        # 6.返回响应
        return JsonResponse({'code': RETCODE.OK, 'errmsg': "短信发送成功"})


# 登录视图
class LoginView(View):
    """
    :param request:
    :return:
    """

    def get(self, request):

        return render(request, "login.html")

    def post(self, request):
        # 1.接收参数
        mobile = request.POST.get('mobile')
        password = request.POST.get('password')
        remember = request.POST.get('remember')
        # 2.参数的验证
        if not re.match(r'^1[3-9]\d{9}$', mobile):
            return HttpResponseBadRequest("手机号不符合规则")

        if not re.match(r'^[0-9A-Za-z]{8,20}$', password):
            return HttpResponseBadRequest("密码不符合规则，密码为8-20位数字、字母")
        # 3.用户认证登录，采用系统自带的认证方法进行认证，正确返回user，错误返回None
        # 默认的认证方法是针对于username字段进行用户名的判断，当前判断信息是手机号，需要修改认证字段，需要到User模型中进行修改
        user = authenticate(mobile=mobile, password=password)
        if user is None:
            return HttpResponseBadRequest("手机号或密码错误！")
        # 4.状态保持
        login(request, user)
        # 5.根据用户选择的是否记住登录状态来进行判断

        # 6.为了首页显示，需要设置一些cookie信息
        # 根据next参数来进行页面的跳转，有就跳转到含next参数的个人中心页面，没有就跳转到首页
        next_page = request.GET.get('next')
        if next_page:
            response = redirect(next_page)
        else:
            response = redirect(reverse('home:index'))
        if remember != 'on':  # 没有记住用户信息
            # 浏览器关闭之后
            request.session.set_expiry(0)
            response.set_cookie('is_login', True)
            response.set_cookie('username', user.username, max_age=14 * 24 * 3600)
        else:  # 记住了用户信息
            # 默认是记住两周
            request.session.set_expiry(None)
            response.set_cookie('is_login', True, max_age=14 * 24 * 3600)
            response.set_cookie('username', user.username, max_age=14 * 24 * 3600)
        # 7.返回响应
        return response


# 退出视图
class LogoutView(View):
    def get(self, request):
        # 1.session数据清除
        logout(request)
        # 2.cookie数据的部分删除
        response = redirect(reverse('home:index'))
        response.delete_cookie('is_login')
        # 3.跳转到首页
        return response


# 忘记密码视图
class ForgetPasswordView(View):
    def get(self, request):
        return render(request, "forget_password.html")

    def post(self, request):
        # 1.接收数据
        mobile = request.POST.get("mobile")
        password = request.POST.get("password")
        password2 = request.POST.get("password2")
        smscode = request.POST.get("sms_code")
        # 2.验证数据
        if not all([mobile, password, password2, smscode]):
            return HttpResponseBadRequest("参数不全")

        if not re.match(r'^1[3-9]\d{9}$', mobile):
            return HttpResponseBadRequest("手机号不符合要求")

        if not re.match(r'^[0-9A-Za-z]{8,20}$', password):
            return HttpResponseBadRequest("密码不符合要求，请输入8-20位数字、字母密码")

        if password2 != password:
            return HttpResponseBadRequest("密码不一致")

        redis_conn = get_redis_connection('default')
        redis_sms_code = redis_conn.get('sms:%s' % mobile)
        if redis_sms_code is None:
            return HttpResponseBadRequest("短信验证码已过期")

        if redis_sms_code.decode() != smscode:
            return HttpResponseBadRequest("短信验证码错误")
        # 3.根据手机号进行用户信息的查询
        try:
            user = User.objects.get(mobile=mobile)
        # 4.如果手机号未查询出用户信息，则进行新用户的创建
        except User.DoesNotExist:
            try:
                User.objects.create_user(username=mobile, mobile=mobile, password=password)
            except Exception:
                return HttpResponseBadRequest("修改失败，请稍后再试")
        # 5.如果手机号查询出用户信息，则进行用户信息的修改
        else:
            user.set_password = password
            # 注意保存用户信息
            user.save()
        # 6.页面跳转，跳转到登陆页面
        response = redirect(reverse('users:login'))
        # 7.返回响应
        return response


# 用户中心视图
# LoginRequiredMixin封装了判断用户是否登录的操作，未登录则进行默认的跳转，默认跳转链接是：accounts/login/?next=xxx
class UserCenterView(LoginRequiredMixin, View):
    def get(self, request):
        # 获取用户登录的信息
        user = request.user
        # 组织获取用户的信息
        context = {
            'username': user.username,
            'mobile': user.mobile,
            'avatar': user.avatar.url if user.avatar else None,
            'user_desc': user.user_desc,
        }
        return render(request, "center.html", context=context)

    def post(self, request):
        user = request.user
        # 1.接收参数
        # # request.user.username后面这个表示没有接收到新的信息，就还用之前的信息
        username = request.POST.get('username', user.username)
        user_desc = request.POST.get('desc', user.user_desc)
        avatar = request.FILES.get('avatar', user.avatar)
        # 2.将参数保存起来
        try:
            user.username = username
            user.user_desc = user_desc
            if avatar:
                user.avatar = avatar
            user.save()
        except Exception as e:
            logger.error(e)
            return HttpResponseBadRequest("修改失败，请稍后再试")
        # 3.更新cookie中的username信息
        # 4.刷新当前页面（重定向操作）
        response = redirect(reverse('users:center'))
        response.set_cookie('username', user.username, max_age=14 * 24 * 3600)
        # 5.返回响应
        return response


# 写博客视图
class WriteBlogView(LoginRequiredMixin, View):
    def get(self, request):
        # 查询所有分类模型
        categories = ArticleCategory.objects.all()
        context = {
            'categories': categories
        }
        return render(request, "write_blog.html", context=context)

    def post(self, request):
        # 1.接收数据
        avatar = request.FILES.get('avatar')
        title = request.POST.get('title')
        category_id = request.POST.get('category')
        tags = request.POST.get('tags')
        summary = request.POST.get('summary')
        content = request.POST.get('content')
        user = request.user
        # 2.验证数据
        if not all([avatar, title, category_id, summary, content]):
            return HttpResponseBadRequest("参数不全")
        # 判断分类id
        try:
            category = ArticleCategory.objects.get(id=category_id)
        except ArticleCategory.DoesNotExist:
            return HttpResponseBadRequest("没有此分类")
        # 3.数据入库
        try:
            article = Article.objects.create(
                author=user,
                avatar=avatar,
                title=title,
                category=category,
                tags=tags,
                summary=summary,
                content=content,
            )
        except Exception as e:
            logger.error(e)
            return HttpResponseBadRequest("发布失败，请稍后再试")
        # 4.跳转到指定页面
        return redirect(reverse('home:index'))
