#!/usr/bin/env python
# Author: 'JiaChen'

import requests

# 使用requests请求https出现警告，做的设置
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


class SaltStackApi(object):
    """saltstack管理操作类"""
    def __init__(self, url, username, password):
        """
        构造函数
        :param url: salt api url
        :param username: 用户名
        :param password: 密码
        """
        self.url = url
        self.username = username
        self.password = password
        self.headers = {
            'Content-type': 'application/json'
        }
        self.login()

    def login(self):
        """
        远程连接salt api服务器并将token值存入headers中
        :return:
        """
        try:
            login_url = self.url + 'login'
            login_params = {'username': self.username, 'password': self.password, 'eauth': 'pam'}
            token = self.get_data(url=login_url, params=login_params)['token']
            self.headers['X-Auth-Token'] = token
        except Exception as e:
            exit('登录失败,请检查salt url或用户名和密码')

    def get_data(self, url, params):
        """
        获取数据
        :param url: 请求地址
        :param params: 请求参数,{}
        :return: 返回数据
        """
        try:
            request = requests.post(url=url, json=params, headers=self.headers,  verify=False)
            response = request.json()
            result = dict(response)
            return result['return'][0]
        except Exception as e:
            exit('获取数据失败,%s' % str(e))

    def salt_command(self, tgt, fun, arg=None, expr_form='glob'):
        """
        远程执行命令
        :param tgt: 匹配minion
        :param fun: 执行模块的函数
        :param arg: 函数的参数
        :param expr_form: tgt匹配规则
        :return:
        """
        try:
            if arg:
                params = {'client': 'local', 'tgt': tgt, 'fun': fun, 'arg': arg, 'expr_form': expr_form}
            else:
                params = {'client': 'local', 'tgt': tgt, 'fun': fun, 'expr_form': expr_form}
            result = self.get_data(url=self.url, params=params)
            return result
        except Exception as e:
            exit('远程执行命令失败,%s' % str(e))

    def salt_async_command(self, tgt, fun, arg=None, expr_form='glob'):
        """
        远程异步执行命令
        :param tgt: 匹配minion
        :param fun: 执行模块的函数
        :param arg: 函数的参数
        :param expr_form: tgt匹配规则
        :return:
        """
        try:
            if arg:
                params = {'client': 'local_async', 'tgt': tgt, 'fun': fun, 'arg': arg, 'expr_form': expr_form}
            else:
                params = {'client': 'local_async', 'tgt': tgt, 'fun': fun, 'expr_form': expr_form}
            jid = self.get_data(url=self.url, params=params)['jid']
            return jid
        except Exception as e:
            exit('远程异步执行命令失败,%s' % str(e))

    def look_jid(self, jid):
        """
        根据异步执行命令返回的jid查看事件结果
        :param jid: 任务jid
        :return:
        """
        try:
            params = {'client': 'runner', 'fun': 'jobs.lookup_jid', 'jid': jid}
            result = self.get_data(url=self.url, params=params)
            return result
        except Exception as e:
            exit('jid[%s]获取任务结果失败,%s' % (jid, str(e)))

if __name__ == '__main__':
    instance = SaltStackApi('https://192.168.222.51:8000/', 'saltapi', 'saltapi')
    result1 = instance.salt_command(tgt='CentOS-01', fun='test.ping')
    print(result1)  # {'CentOS-01': True}
    result2 = instance.salt_command(tgt='CentOS-01,test_system_01', fun='cmd.run', arg='uptime', expr_form='list')
    print(result2)  # {'CentOS-01': ' 14:33:46 up 1 day, 12:32,  2 users,  load average: 0.38, 0.29, 0.26', 'test_system_01': ' 14:33:46 up  1:56,  2 users,  load average: 0.00, 0.02, 0.05'}
    jid1 = instance.salt_async_command(tgt='CentOS-01,CentOS-02,test_system_01', fun='test.ping', expr_form='list')
    result1 = instance.look_jid(jid=jid1)
    print(result1)  # {'test_system_01': True, 'CentOS-01': True}
    jid2 = instance.salt_async_command(tgt='CentOS-01,CentOS-02,test_system_01', fun='cmd.run', arg='uptime', expr_form='list')
    result2 = instance.look_jid(jid=jid2)
    print(result2)  # {'test_system_01': ' 14:33:03 up  1:55,  2 users,  load average: 0.00, 0.03, 0.05', 'CentOS-01': ' 14:33:03 up 1 day, 12:32,  2 users,  load average: 0.39, 0.27, 0.25'}