#!/usr/bin/env python
# Author: 'JiaChen'

import requests

# 使用requests请求https出现警告，做的设置
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

salt_api = 'https://192.168.222.51:8000/'
salt_user = 'saltapi'
salt_password = 'saltapi'


class SaltApi(object):
    """salt api接口"""
    def __init__(self, url, user, password):
        """
        :param url: 请求url
        :param user: salt认证用户名
        :param password: salt认证用户密码
        """
        self.url = url
        self.user = user
        self.password = password
        self.headers = {
            'Content-type': 'application/json'
        }
        self.login_url = self.url + 'login'
        self.params = {'client': 'local', 'fun': '', 'tgt': ''}
        self.login_params = {'username': self.user, 'password': self.password, 'eauth': 'pam'}
        self.token = self.get_data(url=self.login_url, params=self.login_params)['token']
        self.headers['X-Auth-Token'] = self.token

    def get_data(self, url, params):
        """
        获取数据
        :param url: 请求url
        :param params: 关键字参数
        :return:
        """
        request = requests.post(url=url, json=params, headers=self.headers, verify=False)
        response = request.json()
        result = dict(response)
        return result['return'][0]

    def salt_command(self, tgt, fun, arg=None, expr_form='glob'):
        """
        远程执行命令
        :param tgt: 匹配minion
        :param fun: 执行模块的函数
        :param arg: 函数的参数
        :param expr_form: tgt匹配规则
        :return:
        """
        if arg:
            params = {'client': 'local', 'tgt': tgt, 'fun': fun, 'arg': arg, 'expr_form': expr_form}
        else:
            params = {'client': 'local', 'tgt': tgt, 'fun': fun, 'expr_form': expr_form}
        result = self.get_data(url=self.url, params=params)
        return result

    def salt_async_command(self, tgt, fun, arg=None, expr_form='glob'):
        """
        远程异步执行命令
        :param tgt: 匹配minion
        :param fun: 执行模块的函数
        :param arg: 函数的参数
        :param expr_form: tgt匹配规则
        :return:
        """
        if arg:
            params = {'client': 'local_async', 'tgt': tgt, 'fun': fun, 'arg': arg, 'expr_form': expr_form}
        else:
            params = {'client': 'local_async', 'tgt': tgt, 'fun': fun, 'expr_form': expr_form}
        jid = self.get_data(url=self.url, params=params)['jid']
        return jid

    def look_jid(self, jid):
        """
        根据异步执行命令返回的jid查看事件结果
        :param jid: 任务jid
        :return:
        """
        params = {'client': 'runner', 'fun': 'jobs.lookup_jid', 'jid': jid}
        result = self.get_data(url=self.url, params=params)
        return result

obj = SaltApi(salt_api, salt_user, salt_password)
result1 = obj.salt_command(tgt='CentOS-01', fun='test.ping')
result2 = obj.salt_command(tgt='CentOS-01,CentOS-02', fun='cmd.run', arg='uptime', expr_form='list')
jid1 = obj.salt_async_command(tgt='CentOS-01,CentOS-02', fun='test.ping', expr_form='list')
result1 = obj.look_jid(jid=jid1)
jid2 = obj.salt_async_command(tgt='CentOS-01,CentOS-02', fun='cmd.run', arg='uptime', expr_form='list')
result2 = obj.look_jid(jid=jid2)