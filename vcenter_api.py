#!/usr/bin/env python
# Author: 'JiaChen'

import atexit
import ssl
import time
from pyVmomi import vim, vmodl
from pyVim.connect import SmartConnect, Disconnect
from tools import tasks


class VCenterApi(object):
    """vcenter管理操作类"""
    def __init__(self, vcenter_server, vcenter_username, vcenter_password, port=443):
        """
        构造函数
        :param url: vcenter api url
        :param username: 用户名
        :param password: 密码
        """
        self.vcenter_server = vcenter_server
        self.vcenter_username = vcenter_username
        self.vcenter_password = vcenter_password
        self.port = port
        self.si, self.content  = self.connect_to_vcenter()

    def connect_to_vcenter(self):
        """
        远程连接vcenter api服务器并获取si, content
        :return: instace and content
        """
        try:
            context = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
            context.verify_mode = ssl.CERT_NONE
            # 获取连接对象
            si = SmartConnect(host=self.vcenter_server,
                              user=self.vcenter_username,
                              pwd=self.vcenter_password,
                              port=self.port,
                              sslContext=context)
            # 断开连接
            atexit.register(Disconnect, si)
            content = si.RetrieveContent()
            return si, content

        except Exception as e:
            exit('登录失败,请检查vcenter url或用户名和密码')

    def list_obj(self, vimtype):
        """

        :param vimtype:
        :return:
        """
        container = self.content.viewManager.CreateContainerView(self.content.rootFolder, vimtype, True)
        return container.view

    def get_obj(self, vimtype, name):
        """

        :param vimtype:
        :param name:
        :return:
        """
        obj = None
        container = self.content.viewManager.CreateContainerView(self.content.rootFolder, vimtype, True)
        for c in container.view:
            if c.name == name:
                obj = c
                break
        return obj

    def create_vm(self, vm_name, vm_folder, resource_pool, datastore_name):
        """
        创建一台不完整的虚拟机
        :param vm_name: 虚拟机名称
        :param vm_folder: 虚拟机文件夹
        :param resource_pool: esxi上资源池
        :param datastore_name: esxi上数据存储名称
        :return:
        """
        # 定义vm存储目录
        datastore_path = '[' + datastore_name + '] ' + vm_name
        # bare minimum VM shell, no disks. Feel free to edit
        vmx_file = vim.vm.FileInfo(logDirectory=None,
                                   snapshotDirectory=None,
                                   suspendDirectory=None,
                                   vmPathName=datastore_path)
        # 配置vm boot配置
        config = vim.vm.ConfigSpec(name=vm_name,
                                   memoryMB=1024,
                                   numCPUs=4,   # 总核数
                                   numCoresPerSocket=2,     # 几颗CPU
                                   files=vmx_file,
                                   guestId='centos64Guest',
                                   version='vmx-08')
        # 创建虚拟机
        task = vm_folder.CreateVM_Task(config=config, pool=resource_pool)
        tasks.wait_for_tasks(self.si, [task])

    def add_nic(self, vm, network_name):
        """
        添加网卡
        :param network_name: esxi上网卡名称
        :return:
        """
        spec = vim.vm.ConfigSpec()
        nic_spec = vim.vm.device.VirtualDeviceSpec()
        nic_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
        nic_spec.device = vim.vm.device.VirtualVmxnet3()
        nic_spec.device.deviceInfo = vim.Description()
        nic_spec.device.backing = vim.vm.device.VirtualEthernetCard.NetworkBackingInfo()
        nic_spec.device.backing.useAutoDetect = False
        nic_spec.device.backing.network = self.get_obj([vim.Network], network_name)
        nic_spec.device.backing.deviceName = network_name
        nic_spec.device.connectable = vim.vm.device.VirtualDevice.ConnectInfo()
        nic_spec.device.connectable.startConnected = True
        nic_spec.device.connectable.startConnected = True
        nic_spec.device.connectable.allowGuestControl = True
        nic_spec.device.connectable.connected = True
        nic_spec.device.connectable.status = 'untried'
        nic_spec.device.wakeOnLanEnabled = True
        nic_spec.device.addressType = 'generated'
        spec.deviceChange = [nic_spec]
        task = vm.ReconfigVM_Task(spec=spec)
        tasks.wait_for_tasks(self.si, [task])

    def add_scsi(self, vm):
        """
        添加scsi控制器
        :param vm: virtual machine object
        :return: scsi configuration
        :TBD
        """
        spec = vim.vm.ConfigSpec()
        scsi_spec = vim.vm.device.VirtualDeviceSpec()
        scsi_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
        scsi_spec.device = vim.vm.device.VirtualLsiLogicController()
        scsi_spec.device.deviceInfo = vim.Description()
        scsi_spec.device.slotInfo = vim.vm.device.VirtualDevice.PciBusSlotInfo()
        scsi_spec.device.slotInfo.pciSlotNumber = 16
        scsi_spec.device.controllerKey = 100
        scsi_spec.device.unitNumber = 3
        scsi_spec.device.busNumber = 0
        scsi_spec.device.hotAddRemove = True
        scsi_spec.device.sharedBus = 'noSharing'
        scsi_spec.device.scsiCtlrUnitNumber = 7
        spec.deviceChange = [scsi_spec]
        task = vm.ReconfigVM_Task(spec=spec)
        tasks.wait_for_tasks(self.si, [task])

    def add_disk(self, vm, disk_size, disk_type):
        """
        添加硬盘
        :param vm:
        :param disk_size: 磁盘大小（GB）
        :param disk_type: 磁盘类型
        :return:
        """
        spec = vim.vm.ConfigSpec()
        # get all disks on a VM, set unit_number to the next available
        unit_number = 0
        for dev in vm.config.hardware.device:
            if hasattr(dev.backing, 'fileName'):
                unit_number = int(dev.unitNumber) + 1
                # unit_number 7 reserved for scsi controller
                if unit_number == 7:
                    unit_number += 1
                if unit_number >= 16:
                    return
            if isinstance(dev, vim.vm.device.VirtualSCSIController):
                controller = dev
        # add disk here
        new_disk_kb = int(disk_size) * 1024 * 1024
        disk_spec = vim.vm.device.VirtualDeviceSpec()
        disk_spec.fileOperation = "create"
        disk_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
        disk_spec.device = vim.vm.device.VirtualDisk()
        disk_spec.device.backing = vim.vm.device.VirtualDisk.FlatVer2BackingInfo()
        if disk_type == 'thin':
            disk_spec.device.backing.thinProvisioned = True
        disk_spec.device.backing.diskMode = 'persistent'
        disk_spec.device.unitNumber = unit_number
        disk_spec.device.capacityInKB = new_disk_kb
        disk_spec.device.controllerKey = controller.key
        spec.deviceChange = [disk_spec]
        task = vm.ReconfigVM_Task(spec=spec)
        tasks.wait_for_tasks(self.si, [task])

    def add_cdrom(self, vm):
        """
        添加CDROM
        :param vm:
        :return:
        """
        # 查找设备控制器
        for dev in vm.config.hardware.device:
            if isinstance(dev, vim.vm.device.VirtualIDEController):
                # If there are less than 2 devices attached, we can use it.
                if len(dev.device) < 2:
                    controller = dev
                else:
                    controller = None
        # 判断vm是否已经挂载CD-Rom
        for dev in vm.config.hardware.device:
            if isinstance(dev, vim.vm.device.VirtualCdrom):
                cdrom = dev
            else:
                cdrom = None
        # 生成CD-Rom配置
        if cdrom is None:
            spec = vim.vm.ConfigSpec()
            cdrom_spec = vim.vm.device.VirtualDeviceSpec()
            cdrom_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
            cdrom_spec.device = vim.vm.device.VirtualCdrom()
            cdrom_spec.device.deviceInfo = vim.Description()
            cdrom_spec.device.backing = vim.vm.device.VirtualCdrom.RemotePassthroughBackingInfo()
            cdrom_spec.device.connectable = vim.vm.device.VirtualDevice.ConnectInfo()
            cdrom_spec.device.connectable.allowGuestControl = True
            cdrom_spec.device.connectable.startConnected = True
            cdrom_spec.device.controllerKey = controller.key
            cdrom_spec.device.key = -1
            spec.deviceChange = [cdrom_spec]
            task = vm.ReconfigVM_Task(spec=spec)
            tasks.wait_for_tasks(self.si, [task])

    def add_floppy(self, vm):
        # 查找设备控制器
        for dev in vm.config.hardware.device:
            if isinstance(dev, vim.vm.device.VirtualIDEController):
                # If there are less than 2 devices attached, we can use it.
                if len(dev.device) < 2:
                    controller = dev
                else:
                    controller = None
        spec = vim.vm.ConfigSpec()
        floppy_spec = vim.vm.device.VirtualDeviceSpec()
        floppy_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
        floppy_spec.device = vim.vm.device.VirtualFloppy()
        floppy_spec.device.deviceInfo = vim.Description()
        floppy_spec.device.backing = vim.vm.device.VirtualFloppy.RemoteDeviceBackingInfo()
        floppy_spec.device.connectable = vim.vm.device.VirtualDevice.ConnectInfo()
        floppy_spec.device.connectable.allowGuestControl = True
        floppy_spec.device.connectable.startConnected = False
        floppy_spec.device.controllerKey = controller.key
        floppy_spec.device.key = 8000
        spec.deviceChange = [floppy_spec]
        task = vm.ReconfigVM_Task(spec=spec)
        tasks.wait_for_tasks(self.si, [task])

    def print_vm_info(self, vm):
        """
        打印虚拟机详情
        :param vm:
        :return:
        """
        summary = vm.summary
        print("Name       : ", summary.config.name)
        print("Template   : ", summary.config.template)
        print("Path       : ", summary.config.vmPathName)
        print("Guest      : ", summary.config.guestFullName)
        print("Instance UUID : ", summary.config.instanceUuid)
        print("Bios UUID     : ", summary.config.uuid)
        annotation = summary.config.annotation
        if annotation:
            print("Annotation : ", annotation)
        print("State      : ", summary.runtime.powerState)
        if summary.guest is not None:
            ip_address = summary.guest.ipAddress
            tools_version = summary.guest.toolsStatus
            if tools_version is not None:
                print("VMware-tools: ", tools_version)
            else:
                print("Vmware-tools: None")
            if ip_address:
                print("IP         : ", ip_address)
            else:
                print("IP         : None")
        if summary.runtime.question is not None:
            print("Question  : ", summary.runtime.question.text)
        print("")

    def answer_vm_question(self, vm):
        choices = vm.runtime.question.choice.choiceInfo
        default_option = None
        choice = ""
        if vm.runtime.question.choice.defaultIndex is not None:
            ii = vm.runtime.question.choice.defaultIndex
            default_option = choices[ii]
            choice = None
        while choice not in [o.key for o in choices]:
            print("VM power on is paused by this question:\n\n")
            for option in choices:
                print("\t %s: %s " % (option.key, option.label))
            if default_option is not None:
                print("default (%s): %s\n" % (default_option.label, default_option.key))
            choice = input("\nchoice number: ").strip()
            print("...")
        return choice

    def poweroff(self, vm):
        """
        关闭虚拟机
        :param vm:
        :return:
        """
        task = vm.PowerOff()
        actionName = 'job'
        while task.info.state not in [vim.TaskInfo.State.success or vim.TaskInfo.State.error]:
            time.sleep(2)
        if task.info.state == vim.TaskInfo.State.success:
            out = '%s completed successfully.' % actionName
            print(out)
        elif task.info.state == vim.TaskInfo.State.error:
            out = 'Error - %s did not complete successfully: %s' % (actionName, task.info.error)
            raise ValueError(out)
        return

    def poweron(self, vm):
        task = vm.PowerOn()
        actionName = 'job'
        answers = {}
        while task.info.state not in [vim.TaskInfo.State.success or vim.TaskInfo.State.error]:
            if vm.runtime.question is not None:
                question_id = vm.runtime.question.id
                if question_id not in answers.keys():
                    answers[question_id] = self.answer_vm_question(vm)
                    vm.AnswerVM(question_id, answers[question_id])
            time.sleep(2)
        if task.info.state == vim.TaskInfo.State.success:
            out = '%s completed successfully.' % actionName
            print(out)
        elif task.info.state == vim.TaskInfo.State.error:
            out = 'Error - %s did not complete successfully: %s' % (actionName, task.info.error)
            raise ValueError(out)
        return

    def powersuspend(self, vm):
        """
        暂停虚拟机
        :param vm:
        :return:
        """
        if vm.runtime.powerState == 'poweredOn':
            vm.Suspend()

if __name__ == '__main__':
    # 实例化
    instance = VCenterApi(vcenter_server='192.168.222.10',
                          vcenter_username='root',
                          vcenter_password='test@2015',
                          port=443)
    # 获取数据中心
    datacenter = instance.content.rootFolder.childEntity[0]
    # 获取数据中心的文件夹(vm)
    vm_folder = datacenter.vmFolder
    # 获取esxi资源池实例
    resource_obj_list = instance.list_obj([vim.ResourcePool])
    resource_obj = resource_obj_list[0]
    resource_pool = resource_obj
    # 获取esxi主机系统实例
    esxi_obj = instance.get_obj([vim.HostSystem], '192.168.222.20')
    # vm_obj = esxi_obj.vm[1]
    # print(vm_obj.config)
    # 获取esxi网卡名称
    network_name = esxi_obj.network[0].name
    # 获取esxi数据存储
    datastore_name = esxi_obj.datastore[0].name
    # 设置vm_name
    vm_name = 'test_vm_01'
    # 创建一个不完整的vm
    # instance.create_vm(vm_name=vm_name,
    #                    vm_folder=vm_folder,
    #                    resource_pool=resource_pool,
    #                    datastore_name=datastore_name)
    # 通过vm uuid过滤虚拟机
    search_index = instance.si.content.searchIndex
    vm = search_index.FindByUuid(None, '500d8ca6-ee47-95b6-fe3e-2407cd88362f', True, True)
    # 创建网卡
    # instance.add_nic(vm=vm, network_name=network_name)
    # 创建SCSI控制器
    # instance.add_scsi(vm=vm)
    # 创建磁盘(磁盘大小单位GB,类型可选项：thin,thick)
    # thin:虚拟硬盘实际大小随着使用量而浮动，直到使用到硬盘分配上限
    # thick:创建虚拟硬盘是一次性分配完全
    # instance.add_disk(vm, 20, 'thin')
    # 创建光驱
    # instance.add_cdrom(vm=vm)
    # 创建软驱
    # instance.add_floppy(vm=vm)
    # 打印虚拟机详情
    # content = instance.si.RetrieveContent()
    # container = content.rootFolder
    # viewType = [vim.VirtualMachine]
    # recursive = True
    # containerView = content.viewManager.CreateContainerView(container, viewType, recursive)
    # # 遍历虚拟机列表打印虚拟机详情
    # children = containerView.view
    # for child in children:
    #     instance.print_vm_info(child)
    # 打开虚拟机
    # instance.poweron(vm=vm)
    # 关闭虚拟机
    # instance.poweroff(vm=vm)
    # 挂起虚拟机
    # instance.powersuspend(vm=vm)

    esxi_host = {}
    content = instance.si.RetrieveContent()
    esxi_obj = instance.list_obj([vim.HostSystem])
    for esxi in esxi_obj:
        esxi_host[esxi.name] = {'esxi_info': {}, 'datastore': {}, 'network': {}, 'vm': {}}

        esxi_host[esxi.name]['esxi_info']['厂商'] = esxi.summary.hardware.vendor
        esxi_host[esxi.name]['esxi_info']['型号'] = esxi.summary.hardware.model
        for i in esxi.summary.hardware.otherIdentifyingInfo:
            if isinstance(i, vim.host.SystemIdentificationInfo):
                esxi_host[esxi.name]['esxi_info']['SN'] = i.identifierValue
        esxi_host[esxi.name]['esxi_info']['处理器'] = '数量：%s 核数：%s 线程数：%s 频率：%s(%s) ' % (esxi.summary.hardware.numCpuPkgs,
                                                                                      esxi.summary.hardware.numCpuCores,
                                                                                      esxi.summary.hardware.numCpuThreads,
                                                                                      esxi.summary.hardware.cpuMhz,
                                                                                      esxi.summary.hardware.cpuModel)
        esxi_host[esxi.name]['esxi_info']['处理器使用率'] = '%.1f%%' % (esxi.summary.quickStats.overallCpuUsage /
                                                                  (
                                                                  esxi.summary.hardware.numCpuPkgs * esxi.summary.hardware.numCpuCores * esxi.summary.hardware.cpuMhz) * 100)
        esxi_host[esxi.name]['esxi_info']['内存(MB)'] = esxi.summary.hardware.memorySize / 1024 / 1024
        esxi_host[esxi.name]['esxi_info']['可用内存(MB)'] = '%.1f MB' % (
        (esxi.summary.hardware.memorySize / 1024 / 1024) - esxi.summary.quickStats.overallMemoryUsage)
        esxi_host[esxi.name]['esxi_info']['内存使用率'] = '%.1f%%' % (
        (esxi.summary.quickStats.overallMemoryUsage / (esxi.summary.hardware.memorySize / 1024 / 1024)) * 100)
        esxi_host[esxi.name]['esxi_info']['系统'] = esxi.summary.config.product.fullName

        for ds in esxi.datastore:
            esxi_host[esxi.name]['datastore'][ds.name] = {}
            esxi_host[esxi.name]['datastore'][ds.name]['总容量(G)'] = int((ds.summary.capacity) / 1024 / 1024 / 1024)
            esxi_host[esxi.name]['datastore'][ds.name]['空闲容量(G)'] = int((ds.summary.freeSpace) / 1024 / 1024 / 1024)
            esxi_host[esxi.name]['datastore'][ds.name]['类型'] = (ds.summary.type)
        for nt in esxi.network:
            esxi_host[esxi.name]['network'][nt.name] = {}
            esxi_host[esxi.name]['network'][nt.name]['标签ID'] = nt.name
        for vm in esxi.vm:
            esxi_host[esxi.name]['vm'][vm.name] = {}
            esxi_host[esxi.name]['vm'][vm.name]['电源状态'] = vm.runtime.powerState
            esxi_host[esxi.name]['vm'][vm.name]['CPU(内核总数)'] = vm.config.hardware.numCPU
            esxi_host[esxi.name]['vm'][vm.name]['内存(总数MB)'] = vm.config.hardware.memoryMB
            esxi_host[esxi.name]['vm'][vm.name]['系统信息'] = vm.config.guestFullName
            if vm.guest.ipAddress:
                esxi_host[esxi.name]['vm'][vm.name]['IP'] = vm.guest.ipAddress
            else:
                esxi_host[esxi.name]['vm'][vm.name]['IP'] = '服务器需要开机后才可以获取'

            for d in vm.config.hardware.device:
                if isinstance(d, vim.vm.device.VirtualDisk):
                    esxi_host[esxi.name]['vm'][vm.name][d.deviceInfo.label] = str(
                        (d.capacityInKB) / 1024 / 1024) + ' GB'

    print(esxi_host)

'''
{
    '192.168.222.20': {
        'datastore': {
            'datastore1': {
                '总容量(G)': 32, 
                '类型': 'VMFS', 
                '空闲容量(G)': 31
            }
        },
        'esxi_info': {
            '可用内存(MB)': '930.5 MB',
            '处理器': '数量：2 核数：4 线程数：4 频率：2400(Intel(R) Core(TM) i5-6200U CPU @ 2.30GHz) ',
            '厂商': 'VMware, Inc.', 
            '内存(MB)': 2047.48828125, 
            '处理器使用率': '1.0%', 
            '系统': 'VMware ESXi 5.5.0 build-1331820', 
            'SN': 'VMware-56 4d 29 69 51 ea 01 d8-ac 75 a3 df 4d 84 19 1a', 
            '内存使用率': '54.6%', 
            '型号': 'VMware Virtual Platform'
        }, 
        'vm': {
            '192.168.222.60': {
                '内存(总数MB)': 2048, 
                '系统信息': 'CentOS 4/5/6 (64 位)',
                '硬盘 1': '16.0 GB',
                '电源状态': 'poweredOff', 
                'CPU(内核总数)': 4, 
                'IP': '服务器需要开机后才可以获取'
            }, 
            'test_vm_01': {
                '内存(总数MB)': 512,
                '系统信息': 'CentOS 4/5/6 (64 位)',
                '硬盘 1': '20.0 GB', 
                '电源状态': 'poweredOff',
                'CPU(内核总数)': 4,
                'IP': '服务器需要开机后才可以获取'
            }
        }, 
        'network': {
            'VM Network': {
                '标签ID': 'VM Network'
            }
        }
    }
}
'''

# from pyVmomi import vim,vmodl
# from pyVim.connect import SmartConnect, Disconnect
# import atexit
# import sys
# import time
# import ssl
#
#
# class VCenter:
#     def __init__(self):
#         self.pyVmomi = __import__("pyVmomi")
#         self.vcenter_server = '1.1.1.1'
#         self.vcenter_username = 'test'
#         self.vcenter_password = 'test'
#         self.port = 443
#         self.isDHCP=False,
#         self.vm_ip='10.7.42.91',
#         self.subnet= '255.255.255.0',
#         self.gateway= '10.7.42.40',
#         self.dns= ['company.com', 'company.com'],
#         self.domain= 'esx10g.company.com'
#
#     def add_nic(vm, network):
#         spec = vim.vm.ConfigSpec()
#
#         # add Switch here
#         dev_changes = []
#         switch_spec                = vim.vm.device.VirtualDeviceSpec()
#         switch_spec.operation      = vim.vm.device.VirtualDeviceSpec.Operation.add
#         switch_spec.device         = vim.vm.device.VirtualVmxnet3()
#
#         switch_spec.device.backing = vim.vm.device.VirtualEthernetCard.NetworkBackingInfo()
#         switch_spec.device.backing.useAutoDetect = False
#         switch_spec.device.backing.deviceName = network.name
#         switch_spec.device.backing.network = network
#         switch_spec.device.connectable = vim.vm.device.VirtualDevice.ConnectInfo()
#         switch_spec.device.connectable.startConnected = True
#         switch_spec.device.connectable.connected = True
#
#         dev_changes.append(switch_spec)
#
#         spec.deviceChange = dev_changes
#         output = vm.ReconfigVM_Task(spec=spec)
#         time.sleep(2)
#         print output.info
#
#     def connect_to_vcenter(self):
#         context = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
#         context.verify_mode = ssl.CERT_NONE
#         self.service_instance = SmartConnect(
#                                         host = self.vcenter_server,
#                                         user = self.vcenter_username,
#                                         pwd = self.vcenter_password,
#                                         port = self.port,
#                                         sslContext = context)
#         self.content = self.service_instance.RetrieveContent()
#         atexit.register(Disconnect, self.service_instance)
#
#     def wait_for_task(self, task, actionName='job', hideResult=False):
#          while task.info.state == (self.pyVmomi.vim.TaskInfo.State.running or self.pyVmomi.vim.TaskInfo.State.queued):
#              time.sleep(2)
#          if task.info.state == self.pyVmomi.vim.TaskInfo.State.success:
#              if task.info.result is not None and not hideResult:
#                  out = '%s completed successfully, result: %s' % (actionName, task.info.result)
#                  print out
#              else:
#                  out = '%s completed successfully.' % actionName
#                  print out
#          elif task.info.state == self.pyVmomi.vim.TaskInfo.State.error:
#              out = 'Error - %s did not complete successfully: %s' % (actionName, task.info.error)
#              raise ValueError(out)
#          return task.info.result
#
#     def answer_vm_question(self,vm):
#         choices = vm.runtime.question.choice.choiceInfo
#         default_option = None
#         choice = ""
#         if vm.runtime.question.choice.defaultIndex is not None:
#             ii = vm.runtime.question.choice.defaultIndex
#             default_option = choices[ii]
#             choice = None
#         while choice not in [o.key for o in choices]:
#             print "VM power on is paused by this question:\n\n"
#             for option in choices:
#                 print "\t %s: %s " % (option.key, option.label)
#             if default_option is not None:
#                 print "default (%s): %s\n" % (default_option.label,
#                                               default_option.key)
#             choice = raw_input("\nchoice number: ").strip()
#             print "..."
#         return choice
#
#     def poweroff(self, si, vm):
#         task = vm.PowerOff()
#         actionName = 'job'
#         while task.info.state not in [self.pyVmomi.vim.TaskInfo.State.success or self.pyVmomi.vim.TaskInfo.State.error]:
#             time.sleep(2)
#         if task.info.state == self.pyVmomi.vim.TaskInfo.State.success:
#             out = '%s completed successfully.' % actionName
#             print out
#         elif task.info.state == self.pyVmomi.vim.TaskInfo.State.error:
#             out = 'Error - %s did not complete successfully: %s' % (actionName, task.info.error)
#             raise ValueError(out)
#         return
#
#     def poweron(self, si, vm):
#         task = vm.PowerOn()
#         actionName = 'job'
#         answers = {}
#         while task.info.state not in [self.pyVmomi.vim.TaskInfo.State.success or self.pyVmomi.vim.TaskInfo.State.error]:
#             if vm.runtime.question is not None:
#                 question_id = vm.runtime.question.id
#                 if question_id not in answers.keys():
#                     answers[question_id] = self.answer_vm_question(vm)
#                     vm.AnswerVM(question_id, answers[question_id])
#             time.sleep(2)
#         if task.info.state == self.pyVmomi.vim.TaskInfo.State.success:
#             out = '%s completed successfully.' % actionName
#             print out
#         elif task.info.state == self.pyVmomi.vim.TaskInfo.State.error:
#             out = 'Error - %s did not complete successfully: %s' % (actionName, task.info.error)
#             raise ValueError(out)
#         return
#
#     def set_dvs_mtu(self, dvs, mtu):
#         dvs_config_spec = self.pyVmomi.vim.VmwareDistributedVirtualSwitch.ConfigSpec()
#         dvs_config_spec.configVersion = dvs.config.configVersion
#         dvs_config_spec.maxMtu = int(mtu)
#         task = dvs.ReconfigureDvs_Task(dvs_config_spec)
#         self.wait_for_task(task)
#         print "Successfully reconfigured DVS %s with mtu %s" %(dvs.name, mtu)
#         return dvs
#
#     def get_dvs_portgroup(self, vimtype, portgroup_name, dvs_name):
#         obj = None
#         container = self.content.viewManager.CreateContainerView(self.content.rootFolder, vimtype, True)
#         for c in container.view:
#             if c.name == portgroup_name:
#                 if c.config.distributedVirtualSwitch.name == dvs_name:
#                     obj = c
#                     break
#         return obj
#
#     def list_obj(self, vimtype):
#         container = self.content.viewManager.CreateContainerView(self.content.rootFolder, vimtype, True)
#         return container.view
#
#     def get_obj(self, vimtype, name):
#         obj = None
#         container = self.content.viewManager.CreateContainerView(self.content.rootFolder, vimtype, True)
#         for c in container.view:
#             if c.name == name:
#                 obj = c
#                 break
#         return obj
#
#     def get_folder(self, folder_name=''):
#         """获取文件夹"""
#         folder_list = []
#         if folder_name == '':
#             listOBJ = self.list_obj([vim.Folder])
#         else:
#             listOBJ = self.get_obj([vim.Folder],folder_name)
#         for each in listOBJ:
#             folder_list.append(each)
#         return folder_list
#
#     def get_vcenters(self):
#         """获取所有数据中心"""
#         listOBJ = self.list_obj([vim.Datacenter])
#         vcenters_list = []
#         for each in listOBJ:
#             vcenters_list.append(each)
#         return each
#
#     def get_vcenters_alarm(self):
#         """获取所有数据中心报警"""
#         listOBJ = self.list_obj([vim.Datacenter])
#         vcenters_alarm_dict = {}
#         for i in listOBJ[0].triggeredAlarmState:
#             vcenters_alarm_dict[i.entity.name] =  i.alarm.info.name.decode()
#         return vcenters_alarm_dict
#
#     def get_datastore(self, datastore_name=''):
#         """获取存储"""
#         datastore_list = []
#         if datastore_name == '':
#             listOBJ = self.list_obj([vim.Datastore])
#         else:
#             listOBJ = self.get_obj([vim.Datastore],datastore_name)
#         for each in listOBJ:
#             datastore_list.append(each.name)
#         return datastore_list
#
#     def get_clusters(self,clusters_name=''):
#         """获取所有的集群"""
#         clusters_list = []
#         if clusters_name == '':
#             listOBJ = self.list_obj([vim.ClusterComputeResource])
#         else:
#             listOBJ = self.get_obj([vim.ClusterComputeResource],clusters_name)
#         for each in listOBJ:
#             clusters_list.append(each.name)
#         return clusters_list
#
#     def get_resource_pool(self,resource_pool_name=''):
#         """获取所有的资源池"""
#         resource_pool_list = []
#         if resource_pool_name == '':
#             listOBJ = self.list_obj([vim.ResourcePool])
#         else:
#             listOBJ = self.get_obj([vim.ResourcePool],resource_pool_name)
#         for each in listOBJ:
#             resource_pool_list.append(each.name)
#         return resource_pool_list
#
#     def get_hosts(self):
#         """获取所有的宿主机"""
#         listOBJ = self.list_obj([vim.HostSystem])
#         index = 0
#         for each in listOBJ:
#             tupleVNic=sys._getframe().f_code.co_name, index, each.config.network.vnic
#             for eachvnic in tupleVNic[2]:
#                 index = index + 1
#                 print sys._getframe().f_code.co_name, \
#                     index, \
#                     each, \
#                     eachvnic.portgroup, \
#                     eachvnic.spec.mac, \
#                     eachvnic.spec.ip.ipAddress, eachvnic.spec.ip.subnetMask
#
#     def get_pnic(self):
#         """获取所有的上行口"""
#         listOBJ = self.list_obj([vim.HostSystem])
#         index = 0
#         for each in listOBJ:
#             tuplePNic=sys._getframe().f_code.co_name, index, each.config.network.pnic
#             for eachpnic in tuplePNic[2]:
#                 index = index + 1
#                 print sys._getframe().f_code.co_name, index, each, eachpnic.device
#
#     def get_vswitchs(self):
#         """获取所有的交换机（包括标准交换机和分布式交换机)"""
#         listOBJ = self.list_obj([vim.HostSystem])
#         index = 0
#         for each in listOBJ:
#             tupleVswitch = sys._getframe().f_code.co_name, index, each.config.network.vswitch
#             for eachsw in tupleVswitch[2]:
#                 index = index + 1
#                 print sys._getframe().f_code.co_name, index, eachsw.name
#
#     def get_portgroups(self):
#         """获取所有的交换机端口组（包括标准交换机和分布式交换机)"""
#         listOBJ = self.list_obj([vim.Network])
#         index = 0
#         for each in listOBJ:
#             index = index + 1
#             print sys._getframe().f_code.co_name, index, each
#
#     def get_vns(self):
#         """获取所有的虚拟网络（包括标准交换机端口组和分布式交换机端口组)"""
#         listOBJ = self.list_obj([vim.Network])
#         index = 0
#         for each in listOBJ:
#             index = index + 1
#             print sys._getframe().f_code.co_name, index, each
#
#     def get_dvswitchs(self):
#         """获取所有的分布式交换机"""
#         listOBJ = self.list_obj([vim.DistributedVirtualSwitch])
#         index = 0
#         for each in listOBJ:
#             index = index + 1
#             print sys._getframe().f_code.co_name,index,each
#
#     def get_dvportgroups(self):
#         """获取所有的分布式交换机端口组"""
#         listOBJ = self.list_obj([vim.DistributedVirtualSwitch])
#         index = 0
#         for each in listOBJ:
#             for eachportgroup in each.portgroup:
#                 index = index + 1
#                 print sys._getframe().f_code.co_name,index,eachportgroup
#
#     def get_vnic(self):
#         """获取所有的虚拟网卡"""
#         listOBJ = self.list_obj([vim.VirtualMachine])
#         index = 0
#         for each in listOBJ:
#             index = index + 1
#             vmdeviceList = each.config.hardware.device
#             for eachdevice in vmdeviceList:
#                 index = index + 1
#                 if isinstance(eachdevice, vim.vm.device.VirtualEthernetCard ):
#                     if isinstance( eachdevice.backing,vim.vm.device.VirtualEthernetCard.DistributedVirtualPortBackingInfo ):
#                         print sys._getframe().f_code.co_name,\
#                             index, \
#                             eachdevice.deviceInfo.label, \
#                             eachdevice.macAddress, \
#                             eachdevice.deviceInfo.summary, \
#                             eachdevice.backing.port.portgroupKey
#                     else:
#                         print sys._getframe().f_code.co_name,\
#                             index, \
#                             eachdevice.deviceInfo.label, \
#                             eachdevice.macAddress, \
#                             eachdevice.backing.deviceName, \
#                             eachdevice.backing.network
#
#     def get_allvms(self):
#         """获取所有的虚机"""
#         listOBJ = self.list_obj([vim.VirtualMachine])
#         index = 0
#         for each in listOBJ:
#             index = index + 1
#             print sys._getframe().f_code.co_name,index,each.name
#
#     def print_vm_info(self, virtual_machine, depth=1):
#         """打印虚机信息"""
#         maxdepth = 10
#         if hasattr(virtual_machine, 'childEntity'):
#             if depth > maxdepth:
#                 return
#             vmList = virtual_machine.childEntity
#             for c in vmList:
#                 self.print_vm_info(c, depth + 1)
#             return
#         summary = virtual_machine.summary
#         print "Name       : ", summary.config.name
#         print "Path       : ", summary.config.vmPathName
#         print "Guest      : ", summary.config.guestFullName
#         annotation = summary.config.annotation
#         if annotation:
#             print "Annotation : ", annotation
#         print "State      : ", summary.runtime.powerState
#         if summary.guest is not None:
#             ip_address = summary.guest.ipAddress
#             if ip_address:
#                 print "IP         : ", ip_address
#         if summary.runtime.question is not None:
#             print "Question  : ", summary.runtime.question.text
#         print ""
#
#     def get_acquireTicket(self,virtual_machine):
#         """获取主机Console授权"""
#         acquireTickets_dict = {}
#         listOBJ = self.get_obj([vim.VirtualMachine],virtual_machine)
#         try:
#             acquireTickets = listOBJ.AcquireTicket('webmks')
#         except Exception as err:
#             print 'acquireTickets_err:',err
#         acquireTickets_dict['host'] = acquireTickets.host
#         acquireTickets_dict['port'] = acquireTickets.port
#         acquireTickets_dict['ticket'] = acquireTickets.ticket
#         print acquireTickets_dict
#         return acquireTickets_dict
#
#     def get_hosts_exsi_version(self,virtual_machine):
#         """获得主机Esxi版本"""
#         try:
#             hosts_name = self.get_obj([vim.VirtualMachine],virtual_machine).summary.runtime.host
#             for i in self.list_obj([vim.HostSystem]):
#                 if i == hosts_name:
#                     hosts_ip = i.name
#             listOBJ = self.get_obj([vim.HostSystem],hosts_ip)
#             try:
#                 exsi_version = listOBJ.summary.config.product.fullName
#             except Exception as err:
#                 print err
#                 exsi_version = ''
#         except Exception as err:
#             print err
#             exsi_version = ''
#         return exsi_version

# vcenter = VCenter()
# vcenter.connect_to_vcenter()
# vm_exsi_version = ss.get_hosts_exsi_version(vm) //获取宿主机的Esxi版本，进行判断，目前只支持 Exsi 6.x
# vm_console_info = ss.get_acquireTicket(vm) //获取一些Console授权的信息
# vm_console_host = vm_console_info['host']
# vm_console_port = vm_console_info['port']
# vm_console_ticket = vm_console_info['ticket']
