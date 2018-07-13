#!/usr/bin/env python
# Author: 'JiaChen'

import xmlrpc.client


class CobblerApi(object):
    """cobbler管理操作类"""
    def __init__(self, url, username, password):
        self.url = url
        self.username = username
        self.password = password
        self.remote, self.token = self.login()

    def login(self):
        """
        远程连接cobbler服务器并获取token值
        :return:
        """
        try:
            remote = xmlrpc.client.Server(uri=self.url)
            token = remote.login(self.username, self.password)
            return remote, token
        except Exception as e:
            exit('登录失败,请检查cobbler url或用户名和密码')

    def create_profile(self, profile_name, distro_name, ks_path):
        """
        创建profile
        :param profile_name: profile名称
        :param distro_name: 镜像名称
        :param ks_path: ks模板绝对路径
        :return: 返回profile_id
        """
        try:
            profile_id = self.remote.new_profile(self.token)
            self.remote.modify_profile(profile_id, 'name', profile_name, self.token)
            self.remote.modify_profile(profile_id, 'distro', distro_name, self.token)
            self.remote.modify_profile(profile_id, 'kickstart', ks_path, self.token)
            self.remote.save_profile(profile_id, self.token)
            # 这个做任何操作后，都要必须有
            self.remote.sync(self.token)
            return profile_id
        except Exception as e:
            exit('创建profile失败,%s' % str(e))

    def delete_profile(self, profile_id):
        """
        删除profile
        :param profile_id:
        :return:
        """
        try:
            self.remote.remove_profile(profile_id, self.token)
            self.remote.sync(self.token)
        except Exception as e:
            exit('删除profile失败,%s' % str(e))

    def create_system(self, system_name, hostname, profile,
                      nic_name, mac, ipaddr, gateway, subnet='255.255.255.0', static=1, dns='114.114.114.114'):
        """
        创建一个系统
        :param system_name: 系统名称
        :param hostname: 主机名
        :param profile: profile文件
        :param ks_file_path: ks文件绝对路径
        :param nic_name: 网卡名称
        :param mac: mac地址
        :param ipaddr: ip地址
        :param gateway: 网关
        :param subnet: 子网掩码
        :param static: static为1静止
        :param dns: dns地址
        :return: 返回system_id
        """
        try:
            system_id = self.remote.new_system(self.token)
            self.remote.modify_system(system_id, 'name', system_name, self.token)
            self.remote.modify_system(system_id, 'hostname', hostname, self.token)
            self.remote.modify_system(system_id, 'profile', profile, self.token)
            self.remote.modify_system(system_id, 'modify_interface', {
                'macaddress-%s' % nic_name: mac,
                "ipaddress-%s" % nic_name: ipaddr,
                "Gateway-%s" % nic_name: gateway,
                "subnet-%s" % nic_name: subnet,
                "static-%s" % nic_name: static,
                "dnsname-%s" % nic_name: dns
            }, self.token)
            # 保存系统
            self.remote.save_system(system_id, self.token)
            # 相当于ccobbler sync
            self.remote.sync(self.token)
            return system_id
        except Exception as e:
            exit('创建system失败,%s' % str(e))

    def delete_system(self, system_id):
        """
        删除一个系统
        :param system_id: 系统id
        :return:
        """
        try:
            self.remote.remove_system(system_id, self.token)
            self.remote.sync(self.token)
        except Exception as e:
            exit('删除system失败,%s' % str(e))

if __name__ == '__main__':
    instance = CobblerApi(url='http://192.168.222.51/cobbler_api',
                          username='cobbler',
                          password='123456')
    profile_id = instance.create_profile(profile_name='vm_test',
                                         distro_name='CentOS_6.8-x86_64',
                                         ks_path='/var/lib/cobbler/kickstarts/vm_web.cfg')
    print(profile_id)
    system_id = instance.create_system(system_name='test_system',
                                       hostname='test_system_01',
                                       profile='vm_test',
                                       nic_name='eth0',
                                       mac='00:0C:29:CC:47:6B',
                                       ipaddr='192.168.222.60',
                                       gateway='192.168.222.2')
    print(system_id)
