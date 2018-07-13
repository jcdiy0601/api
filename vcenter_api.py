#!/usr/bin/env python
# Author: 'JiaChen'

from pyVmomi import vim,vmodl
from pyVim.connect import SmartConnect, Disconnect, SmartConnectNoSSL
import atexit
import sys
import time
import ssl


class VCenterApi(object):
    """vcenter管理操作类"""
    def __init__(self, url, username, password):
        """
        构造函数
        :param url: vcenter api url
        :param username: 用户名
        :param password: 密码
        """
        self.url = url
        self.username = username
        self.password = password
        self.port = 443
        self.remote, self.content = self.login()

    def login(self):
        """
        远程连接vcenter api服务器并获取content
        :return: instace and content
        """
        try:
            remote = SmartConnectNoSSL(
                host=self.url,
                user=self.username,
                pwd=self.password,
                port=self.port)
            content = remote.RetrieveContent()
            atexit.register(Disconnect, remote)
            return remote, content
        except Exception as e:
            exit('登录失败,请检查vcenter url或用户名和密码')

if __name__ == '__main__':
    instance = VCenterApi(url='192.168.222.10', username='root', password='test@2015')
