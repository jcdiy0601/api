#!/usr/bin/env python
# Author: 'JiaChen'
"""
本模块用于DELL 服务器IDARC API接口,只用于检测硬件状态，检测硬件包括如下:
    < CPU, 内存， 磁盘， 电源， 风扇， raid卡>
注意：只支持IDRAC版本7和版本8
注意：只提取URL：/redfish/v1/Systems/System.Embedded.1 下的信息
"""

import requests
import json


class idrac_api(object):
    """
    DELL powerEdge服务器IDRAC 7/8 API 硬件监控客户端接口
    """
    def __init__(self, ip, username, passwd):
        self.__ip = ip
        self.__username = username
        self.__passwd = passwd
        # 服务器连接tokin对象
        self.__s_tokin = ''
        # 第一次访问提取的元数据，字典格式
        self.__meta_data_dict = ''

    def conn(self):
        """
        连接服务器
        :return:
        """
        # SSL验证会提示警告，这里进行关闭警告信息的提示
        requests.packages.urllib3.disable_warnings()
        # 初始化一个session连接
        c = requests.Session()
        c.timeout = 60
        # 设置验证信息
        c.auth = (self.__username, self.__passwd)
        # 关闭SSL验证
        c.verify = False
        # 连接IDRAC并进行身份验证和原始数据的提取
        auth_url = 'https://%s/redfish/v1/Systems/System.Embedded.1' % (self.__ip)
        try:
            conn_status = c.get(auth_url)
            # 如果连接成功，将session对象赋予self.__s_tokin，获取的元数据赋予self.__meta_data_dict,否则报错
            if conn_status.ok:
                self.__s_tokin = c
                self.__meta_data_dict = conn_status.json()
            else:
                err_info = conn_status.raise_for_status()
                # print('----->',err_info)
                return '服务器: %s IDRAC连接失败，错误信息：%s' % (self.__ip, err_info)
        except Exception as e:
            return '服务器: %s IDRAC连接失败，错误信息：%s' % (self.__ip, e)

    def memory_status(self):
        '''
        检测内存
        输出格式：MemorySummary {'Status': {'Health': 'OK', 'HealthRollUp': 'OK', 'State': 'Enabled'}, 'TotalSystemMemoryGiB': 64.0}
        :return: 返回内存状态
        '''
        mem_status = self.__meta_data_dict['MemorySummary']['Status']['Health']
        return mem_status

    def cpu_status(self):
        '''
        检测CPU
        输出格式：ProcessorSummary {'Count': 2, 'Model': 'Intel(R) Xeon(R) CPU E5-2660 v3 @ 2.60GHz', 'Status': {'Health': 'OK', 'HealthRollUp': 'OK', 'State': 'Enabled'}}
        :return:返回CPU状态
        '''
        cpu_status = self.__meta_data_dict['ProcessorSummary']['Status']['Health']
        return cpu_status

    def sn(self):
        '''
        提取服务的SN，暂时不需要
        :return: 返回SN码
        '''
        sn_str = self.__meta_data_dict['SKU']
        return sn_str

    def disk_status(self):
        '''
        硬盘检测输出：
        SimpleStorage {'@odata.id': '/redfish/v1/Systems/System.Embedded.1/Storage/Controllers'}
        Status {'Health': 'OK', 'HealthRollUp': 'OK', 'State': 'Enabled'}
        如果总体检测结果为OK，直接返回默认字典
        否则将详细检查每一个磁盘和raid卡，将有故障的设备名称写入返回的字典
        :return: 返回硬盘和raid卡状态
        '''
        disk_result= {'raid_card':'OK','pre_disk':'OK'}
        disk_check = self.__meta_data_dict['Status']['Health']
        if disk_check != 'OK':
            d_url_str = 'https://%s%s' % (self.__ip, self.__meta_data_dict['SimpleStorage']['@odata.id'])
            member_out = self.__s_tokin.get(d_url_str).json()
            member_url_str = 'https://%s%s' % (self.__ip, member_out['Members'][0]['@odata.id'])
            pre_disk_out = self.__s_tokin.get(member_url_str).json()
            if pre_disk_out['Status']['Health'] != 'OK':
                disk_result['raid_card'] = pre_disk_out['Name']
            for pd in pre_disk_out['Devices']:
                if pd['Status']['Health'] != 'OK':
                    disk_result['pre_disk'] = pd['Name']

        return disk_result

    def power_status(self):
        '''
        电源检测
        :return: 返回电源状态
        '''
        pow_status = {}
        power_url_list = self.__meta_data_dict['Links']['PoweredBy']
        for p in power_url_list:
            p_url = 'https://%s%s' % (self.__ip, p['@odata.id'])
            p_dict = self.__s_tokin.get(p_url).json()
            pow_status[p_dict['Name']] = p_dict['Status']['Health']
        return pow_status

    def fan_status(self):
        '''
        风扇检测
        :return:统一返回风扇整体状态
        '''
        fan_status={'fan':'OK'}
        fan_all_list = self.__meta_data_dict['Links']['CooledBy']
        for f in fan_all_list:
            f_url_str = 'https://%s%s' % (self.__ip, f['@odata.id'])
            fan_out = self.__s_tokin.get(f_url_str).json()
            if fan_out['Status']['Health'] != 'OK':
                fan_status['fan'] = fan_out['FanName']
                return fan_status
        return fan_status

    def hardware_status(self):
        '''
        收集所有硬件信息
        :return: 返回json格式数据
        '''
        out = []
        ck_result = {}
        ck_result['cpu'] = self.cpu_status()
        ck_result['memory'] = self.memory_status()
        ck_result['disk'] = self.disk_status()['pre_disk']
        ck_result['raid_card'] = self.disk_status()['raid_card']
        ck_result['power1'] = self.power_status()['PS1 Status']
        ck_result['power2'] = self.power_status()['PS2 Status']
        ck_result['fan'] = self.fan_status()['fan']
        # 提取故障设备
        for s in ck_result:
            if ck_result[s] != 'OK':
                out.append(ck_result[s])
        if len(out) == 0:
            out.append('OK')
        # 以字符串返回故障设备，否则返回OK，表示无故障
        return ','.join(out)

if __name__ == '__main__':
    '''
    运行主程序，测试使用
    '''
    out = idrac_api('IDRAC IP', '账号', '密码')
    # 连接服务器
    mess = out.conn()
    # 有错误就打印报错信息并exit
    if mess:
        exit(mess)
    # 以字符串打印检测结果
    result = out.hardware_status()
    print(result)