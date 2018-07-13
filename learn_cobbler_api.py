#!/usr/bin/env python
# Author: 'JiaChen'

import xmlrpc.client


server = 'http://192.168.222.51/cobbler_api'
user = 'cobbler'
password = '123456'

# 连接cobbler
remote_server = xmlrpc.client.Server(uri=server)
# 登录获取token
remote_token = remote_server.login('cobbler', '123456')
print(remote_token)
print(remote_server.token_check(remote_token))
# profile_id = remote_server.new_profile(remote_token)
# remote_server.modify_profile(profile_id, 'name', 'vm_test', remote_token)
# remote_server.modify_profile(profile_id, 'distro', 'CentOS_6.8-x86_64', remote_token)
# remote_server.modify_profile(profile_id, 'kickstart', '/var/lib/cobbler/kickstarts/vm_web.cfg', remote_token)
# result = remote_server.save_profile(profile_id, remote_token)
# print(result)
#
# remote_server.sync(remote_token)
# print(remote_server.get_kickstart_templates())
# print(remote_server.get_snippets())