# # -*- coding: utf-8 -*-

# import os
# import time
# from pathlib import Path
# from p115client import exception
# import init
# from p115 import P115Client
# from p115client import tool
# import random


# class Client_115:
#     def __init__(self):
#         self.logger = init.logger
#         self.bot_config = init.bot_config
#         self.client = self.initialize_client()

#     def initialize_client(self):
#         """初始化客户端，并检查Cookie有效性"""
#         cookie = self.load_cookie()
#         if not cookie:
#             self.logger.error("无法加载Cookie，文件可能缺失或读取失败")
#             return None

#         # client_115 = P115Client(cookie)
#         client_115 = P115Client(Path(init.COOKIE_FILE).expanduser(), check_for_relogin=True)
#         if not self.verify_cookie(client_115):
#             self.logger.error("Cookie已过期或无效")
#             return None
#         return client_115

#     def load_cookie(self):
#         """加载Cookie文件"""
#         try:
#             cookie_path = Path(init.COOKIE_FILE)
#             return cookie_path.read_text(encoding='utf-8').strip()
#         except FileNotFoundError:
#             self.logger.error("Cookie文件未找到")
#             return None
#         except IOError as e:
#             self.logger.error(f"读取Cookie文件失败: {e}")
#             return None

#     def verify_cookie(self, client_115):
#         """验证Cookie是否有效"""
#         try:
#             tool.fs_files.iter_fs_files(client_115, 0)
#             return True
#         except exception.AuthenticationError as e:
#             init.logger.error(f"认证失败: {e}")
#             return False
#         except Exception as e:
#             init.logger.error(f"认证失败: {e}")
#             return False

#     def upload(self, file_path, pid=0):
#         response = self.client.upload_file(file_path, pid=pid)
#         if response.get('status') == 2 and response.get('statuscode') == 0:
#             self.logger.info("已秒传至115~")
#         else:
#             self.logger.info("已上传至115~")
#         return response

#     def offline_download(self, url):
#         response = self.client.offline_add_url(url)
#         resource_name = self.get_offline_resource_name(url)
#         if response.get('errno') is not None:
#             self.logger.info(f"离线遇到错误！error_type: {response.get('errtype')}！")
#         else:
#             self.logger.info(f"添加离线任务[{resource_name}]成功，")
#         return response, resource_name

#     def check_offline_download_success(self, url, resource_name):
#         tasks = []
#         time_out = 0
#         download_success = False
#         while time_out < 300:
#             tasks.clear()
#             offline_list = self.client.offline_list()
#             tasks = offline_list['tasks']
#             for task in tasks:
#                 if task['url'] == url and task['percentDone'] == 100:
#                         self.logger.info(f"[{resource_name}]离线下载完成!")
#                         download_success = True
#                         return download_success
#             time.sleep(10)
#             time_out += 10
#         self.logger.warn(f"[{resource_name}]离线下载超时!")
#         return download_success


#     def clear_failed_task(self, url, resource_name):
#         offline_list = self.client.offline_list()
#         tasks = offline_list['tasks']
#         try:
#             for task in tasks:
#                 if task['url'] == url:
#                     info_hash = task['info_hash']
#                     self.logger.info(f"正在删除超时/失败的离线任务 (ID: {resource_name})，同时删除源文件...")
#                     response = self.client.offline_remove({
#                         "hash[0]": info_hash,
#                         "flag": 1
#                     })
#                     if response.get('state', False):
#                         self.logger.info(f"成功删除离线任务 (ID: {resource_name}) 及其源文件")
#                     else:
#                         self.logger.warn(f"删除离线任务失败: {response}")
#                     break

#         except Exception as e:
#             self.logger.error(f"清理离线任务时出错: {str(e)}")

#     def get_offline_resource_name(self, url):
#         offline_list = self.client.offline_list()
#         tasks = offline_list['tasks']
#         resource_name = ""
#         for task in tasks:
#             if task['url'] == url:
#                 resource_name = task['name']
#                 break
#         return resource_name

#     def move_file(self, src, dst):
#         if src == dst:
#             return
#         response = self.client.fs.move(src, dst)
#         self.logger.info(f"移动文件成功! [{src}] -> [{dst}]")
#         time.sleep(3)

#     def rename(self, old_name, new_name):
#         response = self.client.fs.rename(old_name, new_name)
#         self.logger.info(f"重命名成功! [{old_name}] -> [{new_name}]")
#         time.sleep(3)

#     def auto_clean(self, path):
#         # 开关关闭直接返回
#         if str(self.bot_config['clean_policy']['switch']).lower() == "off":
#             return
#         # 获取文件列表
#         file_list = self.client.fs.listdir_attr(path)
#         # 换算字节大小
#         byte_size = 0
#         less_than = self.bot_config['clean_policy']['less_than']
#         if less_than is not None:
#             if str(less_than).upper().endswith("M"):
#                 byte_size = int(less_than[:-1]) * 1024 * 1024
#             elif str(less_than).upper().endswith("K"):
#                 byte_size = int(less_than[:-1]) * 1024
#             elif str(less_than).upper().endswith("G"):
#                 byte_size = int(less_than[:-1]) * 1024 * 1024 * 1024
#         # 获取排除的文件类型
#         file_type_list = self.bot_config['clean_policy']['file_type']
#         # 根据策略删除文件
#         for item in file_list:
#             if not item['is_directory']:
#                 # 获取大小单位B
#                 size = item['size']
#                 file_type = item['name'][:-3]
#                 # 根据策略删除文件
#                 if (byte_size > 0 and size < byte_size) or (file_type_list is not None and file_type in file_type_list):
#                     self.client.fs.remove(item['path'])
#                     self.logger.info(f"自动清理文件[{item['path']}]成功.")
#                     time.sleep(3)
#             else:
#                 self.client.fs.rmtree(f"{path}/{item['name']}")
#                 time.sleep(3)

#     def get_files_from_dir(self, path):
#         file_list = []
#         files_attr = self.client.fs.listdir_attr(path)
#         for file_attr in files_attr:
#             if not file_attr['is_directory']:
#                 suffix = os.path.splitext(file_attr['name'])[1]
#                 if suffix in ".mkv;.iso;.ts;.mp4;.avi;.rmvb;.wmv;.m2ts;.mpg;.flv;.rm;.mov":
#                     file_list.append(file_attr['name'])
#         return file_list

#     def get_file_from_path(self, path, file_list, max_delay=3):
#         random_delay = random.randint(1, max_delay)
#         time.sleep(random_delay)
#         list_attr = self.client.fs.listdir_attr(path, file_list)
#         for item in list_attr:
#             if item['is_directory'] is True:
#                 self.get_file_from_path(item['path'], file_list)
#             else:
#                 suffix = os.path.splitext(item['name'])[1]
#                 if suffix in ".mkv;.iso;.ts;.mp4;.avi;.rmvb;.wmv;.m2ts;.mpg;.flv;.rm;.mov":
#                     file_list.append(item['path'])

#     def is_directory(self, path):
#         attr = self.client.fs.attr(path)
#         return attr['is_directory']

#     def create_dir_for_video_file(self, path):
#         temp_path = f"{self.bot_config['offline_path']}/temp"
#         try:
#             attr = self.client.fs.attr(temp_path)
#             self.move_file(path, temp_path)
#         except FileNotFoundError as e:
#             self.client.fs.mkdir(temp_path)
#             time.sleep(3)
#             self.move_file(path, temp_path)

#     def create_folder(self, path):
#         try:
#             attr = self.client.fs.attr(path)
#         except FileNotFoundError as e:
#             self.client.fs.mkdir(path)
#             time.sleep(3)


#     def save_shared_link(self, path: str, share_code: str, receive_code: str):
#         """
#         保存115分享链接中的内容到指定路径
#         """
#         try:
#             # 获取分享的文件系统
#             res = self.client.share_receive({"share_code": share_code, "receive_code": receive_code, "cid": path})
#             if not res:
#                 self.logger.error("获取分享文件系统失败")
#                 return False, []

#             # 获取或创建目标路径
#             try:
#                 path_info = self.client.fs_dir_getid(path)
#                 pid = path_info['id']
#             except Exception as e:
#                 self.logger.info(f"目标路径不存在，正在创建: {path}")
#                 self.create_folder(path)
#                 path_info = self.client.fs_dir_getid(path)
#                 pid = path_info['id']

#             # 获取分享内容的文件列表
#             files_data = share_fs.fs_files({"limit": 1000})

#             if not isinstance(files_data, dict) or 'data' not in files_data or 'list' not in files_data['data']:
#                 self.logger.error("获取分享文件列表失败")
#                 return False, []

#             # 收集所有文件的ID和名称
#             file_ids = []
#             file_names = []
#             total_size = 0

#             for file_info in files_data['data']['list']:
#                 if 'fid' in file_info:  # 文件
#                     file_name = os.path.splitext(file_info['n'])[0]  # 去掉扩展名
#                     self.create_folder(f"{path}/{file_name}")
#                     path_info = self.client.fs_dir_getid(f"{path}/{file_name}")
#                     pid = path_info['id']
#                     file_ids.append(file_info['fid'])
#                     file_names.append(file_info['n'])
#                     total_size += int(file_info.get('s', 0))
#                 elif 'cid' in file_info:  # 文件夹
#                     file_ids.append(file_info['cid'])
#                     file_names.append(file_info['n'])
#                     total_size += int(file_info.get('s', 0))
#                 else:
#                     self.logger.error(f"文件[{file_info.get('n', 'unknown')}]结构异常，暂不支持保存")
#                     return False, []

#                 self.logger.info(
#                     f"准备保存{'文件' if 'fid' in file_info else '文件夹'}: {file_info['n']} "
#                     f"(大小: {self._format_size(file_info['s'])})"
#                 )

#             if not file_ids:
#                 self.logger.warning("分享链接中没有可保存的文件")
#                 return True, []

#             # 批量接收文件到指定目录
#             result = share_fs.receive(file_ids, to_pid=pid)

#             if not result.get('state', False):
#                 self.logger.error(f"保存文件失败: {result}")
#                 return False, []

#             self.logger.info(
#                 f"成功保存 {len(file_names)} 个文件到 {path}\n"
#                 f"总大小: {self._format_size(total_size)}\n"
#                 f"文件列表: {', '.join(file_names)}"
#             )

#             return True, file_names

#         except Exception as e:
#             self.logger.error(f"保存分享链接失败: {str(e)}")
#             return False, []

#     def _format_size(self, size_in_bytes: int) -> str:
#         """将字节大小转换为人类可读格式"""
#         for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
#             if size_in_bytes < 1024:
#                 return f"{size_in_bytes:.2f} {unit}"
#             size_in_bytes /= 1024
#         return f"{size_in_bytes:.2f} PB"


#     # def get_file_from_path(self, path, file_list, max_delay=3):
#     #     if path.endswith("/"):
#     #         path = path[:-1]
#     #     random_delay = random.randint(1, max_delay)
#     #     time.sleep(random_delay)
#     #     path_id = self.client.fs_dir_getid(path)['id']
#     #     list_attr = self.client.fs_files(path_id)
#     #     for item in list_attr['data']:
#     #         if 'fid' not in item.keys():
#     #             self.get_file_from_path(f"{path}/{item['n']}", file_list)
#     #         else:
#     #             suffix = os.path.splitext(item['n'])[1]
#     #             if suffix in ".mkv;.iso;.ts;.mp4;.avi;.rmvb;.wmv;.m2ts;.mpg;.flv;.rm;.mov":
#     #                 file_list.append(f"{path}/{item['n']}")


# if __name__ == '__main__':
#     init.init_log()
#     client = Client_115()
#     client.save_shared_link("/云下载", "swwbinv33n4", "uaf6")
