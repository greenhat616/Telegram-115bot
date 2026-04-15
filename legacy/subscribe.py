# # -*- coding: utf-8 -*-

# import requests
# import init
# import time
# from datetime import datetime
# from sqlitelib import *
# from bs4 import BeautifulSoup
# from telegram import Bot
# from message_queue import add_task_to_queue
# import yaml
# from download_handler import create_strm_file, notice_emby_scan_library
# from telegram.helpers import escape_markdown


# def get_actor_id(actor_name):
#     # JavDB 演员搜索 URL
#     search_url = f"https://javdb.com/search?q={actor_name}&f=actor"

#     headers = {
#         "User-Agent": init.USER_AGENT
#     }

#     try:
#         # 发起 GET 请求
#         response = requests.get(search_url, headers=headers)

#         if response.status_code != 200:
#             init.logger.error(f"请求[actor_id]失败，响应状态码: {response.status_code}")
#             return None

#         response.raise_for_status()

#         # 使用 BeautifulSoup 解析 HTML
#         soup = BeautifulSoup(response.text, "html.parser")

#         # 搜索所有演员链接，链接中包含 "/actor/"
#         actor_link = soup.find("a",
#                                href=lambda href: href and "/actors/" in href,
#                                title=lambda title: title and actor_name in title)

#         # 如果找到链接，提取第一个演员 ID
#         if actor_link:
#             actor_id = actor_link["href"].split("/")[-1]  # 提取 ID
#             return actor_id
#         else:
#             init.logger.warn("未找到演员链接，请检查演员名字或 HTML 结构。")
#             return None

#     except requests.exceptions.RequestException as e:
#         init.logger.error(f"请求失败: {e}")
#         return None


# def del_all_subscribe():
#     with SqlLiteLib() as sqlite:
#         sql = f"delete from subscribe"
#         sqlite.execute_sql(sql)
#         init.logger.info("All subscribe has been deleted.")

# def del_sub_by_actor(actor_id, actor_name):
#     with SqlLiteLib() as sqlite:
#         sql = f"delete from subscribe where actor_id = ?"
#         param = (actor_id,)
#         sqlite.execute_sql(sql, param)
#         init.logger.info(f"[{actor_name}] has been deleted.")


# def update_pub_url(number, pub_url):
#     with SqlLiteLib() as sqlite:
#         sql = f"update subscribe set pub_url=? where number=?"
#         params = (pub_url, number)
#         sqlite.execute_sql(sql, params)


# def add_subscribe2db(actor_name, sub_user):
#     actor_id = get_actor_id(actor_name)
#     if not actor_id:
#         init.logger.error(f"添加订阅[{actor_name}]失败！")
#         return
#     headers = {
#         "user-agent": init.USER_AGENT,
#         "cookie": init.JAVDB_COOKIE,
#         "origin": "https://javdb.com"
#     }
#     base_url = f"https://javdb.com/actors/{actor_id}"
#     max_pages = 10
#     with SqlLiteLib() as sqlite:
#         query = f"select number from subscribe where actor_id = ?"
#         params = (actor_id,)
#         res = sqlite.query(query, params)
#         for page in range(1, max_pages + 1):
#             url = f"{base_url}?page={page}&sort_type=0"
#             init.logger.info(f"Get info from {url}")
#             response = requests.get(url, headers=headers)

#             if response.status_code != 200:
#                 init.logger.warn(f"Failed to fetch data for actor {actor_name}, page {page}")
#                 return ""

#             soup = BeautifulSoup(response.text, features="html.parser")
#             movie_list_div = soup.find('div', class_='movie-list h cols-4 vcols-8')
#             if not movie_list_div:
#                 init.logger.info("No movies found or structure mismatch.")
#                 break

#             item_divs = movie_list_div.findAll('div', class_='item')
#             if not item_divs:
#                 init.logger.info("No items found in movie list.")
#                 break

#             for item_div in item_divs:
#                 # 提取图片链接
#                 img_tag = item_div.find('img')
#                 post_url = img_tag['src'] if img_tag and 'src' in img_tag.attrs else ""

#                 # 提取描述并跳过不需要的项
#                 description = item_div.get_text()
#                 if "含中字磁鏈" in description or "含磁鏈" in description:
#                     continue

#                 # 提取番号
#                 video_title_div = item_div.find('div', class_='video-title')
#                 number = video_title_div.find('strong').text if video_title_div else "N/A"

#                 # 提取标题
#                 title = item_div.find('a', class_='box').get('title', "N/A")

#                 # 提取评分
#                 score_div = item_div.find('div', class_='score')
#                 score_text = score_div.find('span', class_='value').text if score_div else "0 分"
#                 score = score_text.split('分')[0].strip()

#                 # 提取日期
#                 meta_div = item_div.find('div', class_='meta')
#                 pub_date = meta_div.text.strip() if meta_div else "未知日期"

#                 if (number,) not in res:
#                     # 插入数据到数据库
#                     insert_sql = f'''INSERT INTO subscribe (actor_name, actor_id, number, pub_date, title, post_url, score, sub_user) VALUES (?,?,?,?,?,?,?,?)'''
#                     init.logger.debug(insert_sql)
#                     params = (actor_name, actor_id, number, pub_date, title, post_url, score, sub_user)
#                     sqlite.execute_sql(insert_sql, params)
#                     init.logger.info(f"[{number}] has been added to subscribe.")
#                 time.sleep(3)


# def get_magnet_by_number(number):
#     headers = {
#         "user-agent": init.USER_AGENT,
#         "cookie": init.JAVDB_COOKIE,
#     }
#     base_url = "https://javdb.com"
#     url = f"{base_url}/search?q={number}&f=all"
#     response = requests.get(url, headers=headers)

#     if response.status_code != 200:
#         init.logger.warn(f"Failed to fetch data for number")
#         return ""

#     soup = BeautifulSoup(response.text, features="html.parser")
#     movie_list_div = soup.find('div', class_='movie-list h cols-4 vcols-8')
#     if not movie_list_div:
#         init.logger.info("No movies found or structure mismatch.")
#         return

#     item_divs = movie_list_div.findAll('div', class_='item')
#     if not item_divs:
#         init.logger.info("No items found in movie list.")
#         return

#     for item_div in item_divs:
#         description = item_div.get_text()
#         if (number in description or number.upper() in description) and ("含中字磁鏈" in description or "含磁鏈" in description):
#             href = item_div.find('a', class_='box').get('href')
#             # 更新发布url
#             update_pub_url(number, f"{base_url}{href}")
#             magnet_link_list = crawl_magnet(f"{base_url}{href}")
#             return magnet_link_list
#     return None


# def crawl_magnet(url):
#     headers = {
#         "user-agent": init.USER_AGENT,
#         "cookie": init.JAVDB_COOKIE,
#     }
#     response = requests.get(url, headers=headers)

#     if response.status_code != 200:
#         init.logger.warn(f"Failed to fetch data for number")
#         return ""

#     magnet_link_list = []

#     soup = BeautifulSoup(response.text, features="html.parser")
#     magnet_div = soup.find('div', class_='magnet-links')

#     item_columns_odd = magnet_div.findAll('div', class_='item columns is-desktop odd')
#     for item_column_odd in item_columns_odd:
#         score = 0.0
#         magnet_link = item_column_odd.find('a').get('href')
#         tags_div = item_column_odd.find('div', class_='tags')
#         if tags_div is not None:
#             for tag in tags_div.find_all('span'):
#                 if '高清' in tag.text:
#                     score += init.bot_config['subscribe']['sub_weight']['hd']
#                 elif '字幕' in tag.text:
#                     score += init.bot_config['subscribe']['sub_weight']['subtitle_zh']
#         date_div = item_column_odd.find('div', class_='date')
#         date = date_div.find('span', class_='time').text
#         score += calculate_score(date)
#         magnet_link_list.append({"score": score, "magnet_link": magnet_link})

#     item_columns = magnet_div.findAll('div', class_='item columns is-desktop')
#     for item_column in item_columns:
#         score = 0.0
#         magnet_link = item_column.find('a').get('href')
#         tags_div = item_column.find('div', class_='tags')
#         if tags_div is not None:
#             for tag in tags_div.find_all('span'):
#                 if '高清' in tag.text:
#                     score += init.bot_config['subscribe']['sub_weight']['hd']
#                 elif '字幕' in tag.text:
#                     score += init.bot_config['subscribe']['sub_weight']['subtitle_zh']
#         date_div = item_column.find('div', class_='date')
#         date = date_div.find('span', class_='time').text
#         score += calculate_score(date)
#         magnet_link_list.append({"score": score, "magnet_link": magnet_link})
#     if magnet_link_list:
#         # 按评级从高到低排序
#         sorted_res_list = sorted(magnet_link_list, key=lambda x: x['score'], reverse=True)
#         return sorted_res_list
#     return None


# def days_since(date_str):
#     # 将输入日期字符串解析为日期对象
#     input_date = datetime.strptime(date_str, "%Y-%m-%d")
#     # 获取今天的日期
#     today = datetime.today()
#     # 计算天数差
#     delta = today - input_date
#     # 返回差值的天数
#     return delta.days


# def calculate_score(date_str):
#     days = days_since(date_str)
#     # 使用评分公式：1 / (1 + days)
#     return 1 / (1 + days)


# # 定时任务，更新订阅演员的订阅列表
# def schedule_actor():
#     actor_list = get_actors()
#     for actor in actor_list:
#         add_subscribe2db(actor['actor_name'], actor['sub_user'])
#         time.sleep(3)


# # 定时任务，定时查看已订阅的演员是否有更新
# def schedule_number():
#     with SqlLiteLib() as sqlite:
#         try:
#             # 查询需要处理的数据
#             query = "SELECT number, actor_name FROM subscribe WHERE is_download = 0"
#             rows = sqlite.query(query)
#             if not rows:
#                 init.logger.info("订阅的老师还木有发布新作呦~")
#                 return
#             for row in rows:
#                 number, actor_name = row
#                 magnet_link_list = get_magnet_by_number(number)
#                 if not magnet_link_list:  # 检查是否返回有效磁力链接列表
#                     init.logger.info(f"[{number}]的磁力链接尚未发布")
#                     continue

#                 # 依次下载，直到成功后退出
#                 for item in magnet_link_list:
#                     magnet_link = item['magnet_link']
#                     init.logger.warn(f"尝试使用[{magnet_link}]离线到115，请稍后...")
#                     # 自动添加到离线下载
#                     if download2spec_path(magnet_link, number, actor_name):
#                         # 更新下载状态和下载链接
#                         update_download_sql = "UPDATE subscribe SET is_download = 1, magnet = ? WHERE number = ?"
#                         sqlite.execute_sql(update_download_sql, (magnet_link, number))

#                         # 发送消息给用户
#                         send_message2usr(number, sqlite)
#                         break
#                     else:
#                         init.logger.warn(f"[{magnet_link}]离线失败，继续尝试使用其它磁力下载...")
#                 # 每次处理完一个任务后等待 10 秒
#                 time.sleep(10)

#         except Exception as e:
#             # 捕获并记录异常
#             init.logger.warn(f"执行定时任务时，出现错误: {e}")

# def send_message2usr(number, sqlite):
#     try:
#         query = "select sub_user,magnet,post_url,actor_name,score,title,pub_url from subscribe where number=?"
#         params = (number,)
#         res = sqlite.query(query, params)
#         if not res:
#             init.logger.warn(f"未找到编号为[{number}]的记录!")
#             return
#         sub_user = res[0][0]
#         magnet = res[0][1]
#         post_url = res[0][2]
#         actor_name= res[0][3]
#         score = res[0][4]
#         title = res[0][5]
#         pub_url = res[0][6]
#         msg_title = escape_markdown(f"[{number}] {title} 订阅已下载!", version=2)
#         msg_actor_name = escape_markdown(actor_name, version=2)
#         msg_score = escape_markdown(str(score), version=2)
#         message = f"""
#                 **{msg_title}**

#                 **演员:** {msg_actor_name}
#                 **评分:** {msg_score}
#                 **下载链接:** `{magnet}`
#                 **发布链接:** [点击查看详情]({pub_url})
#                 """
#         add_task_to_queue(sub_user, post_url, message)
#         init.logger.info(f"[{number}] 加入队列成功！")

#     except Exception as e:
#         init.logger.error(f"编号 [{number}] 添加到队列失败: {e}")


# def download2spec_path(magnet_link, number, actor_name):
#     try:
#         save_path = f"{init.bot_config['subscribe']['path']}/{actor_name}"
#         # 创建目录
#         init.openapi_115.create_dir_for_file(f"{init.bot_config['subscribe']['path']}", actor_name)
#         offline_success = init.openapi_115.offline_download(magnet_link)
#         if not offline_success:
#             init.logger.error(f"❌ 离线遇到错误！")
#         else:
#             init.logger.info(f"✅ [`{magnet_link}`]添加离线成功")
#             download_success, resource_name = init.openapi_115.check_offline_download_success(magnet_link)
#             if download_success:
#                 init.logger.info(f"✅ [{resource_name}]离线下载完成")
#                 if init.openapi_115.is_directory(f"{init.bot_config['offline_path']}/{resource_name}"):
#                     # 清除垃圾文件
#                     init.openapi_115.auto_clean(f"{init.bot_config['offline_path']}/{resource_name}")
#                     # 重名名资源
#                     init.openapi_115.rename(f"{init.bot_config['offline_path']}/{resource_name}", f"{init.bot_config['offline_path']}/{number}")
#                     # 移动文件
#                     init.openapi_115.move_file(f"{init.bot_config['offline_path']}/{number}", save_path)
#                 else:
#                     # 创建番号文件夹
#                     init.openapi_115.create_dir_for_file(f"{init.bot_config['offline_path']}", number)
#                     # 移动文件到番号文件夹
#                     init.openapi_115.move_file(f"{init.bot_config['offline_path']}/{resource_name}", f"{init.bot_config['offline_path']}/{number}")
#                     # 移动番号文件夹到指定目录
#                     init.openapi_115.move_file(f"{init.bot_config['offline_path']}/{number}", save_path)

#                 # 读取目录下所有文件
#                 file_list = init.openapi_115.get_files_from_dir(f"{save_path}/{number}")
#                 # 创建软链
#                 create_strm_file(f"{save_path}/{number}", file_list)
#                 # 通知Emby扫库
#                 notice_emby_scan_library()
#                 return True
#             else:
#                 # 下载超时删除任务
#                 init.openapi_115.clear_failed_task(magnet_link, resource_name)
#                 return False
#     except Exception as e:
#         init.logger.error(f"💀下载遇到错误: {str(e)}")
#         return False
#     finally:
#         # 清除云端任务，避免重复下载
#         init.openapi_115.clear_cloud_task()


# def get_actors():
#     with SqlLiteLib() as sqlite:
#         sql = "select actor_name, sub_user from actor where is_delete=?"
#         params = ("0",)
#         result = sqlite.query(sql, params)
#         return [{"actor_name": row[0], "sub_user": row[1]} for row in result]


# if __name__ == '__main__':
#     init.init_log()
#     actor_id = get_actor_id("三上悠亜")
#     print(actor_id)
#     # init.init()
#     # magnet_link = get_magnet_by_number("OFJE-484")
#     # print(magnet_link)
#     # number = "THU-043"
#     # title = "完全主観×鬼イカせ 8時間BEST vol.01 鈴村あいり 河合あすな 野々浦暖 涼森れむ 八掛うみ"
#     # actor_name = "涼森玲夢"
#     # score = "0.0"
#     # pub_url = "https://javdb.com/v/mOQN1r"
#     # msg_title = escape_markdown(f"[{number}] {title} 订阅已下载!", version=2)
#     # msg_actor_name = escape_markdown(actor_name, version=2)
#     # magnet = "magnet:?xt=urn:btih:57c7be25daec95af868a1be865442226c3385211&dn=[javdb.com]abf-208"
#     # message = f"""
#     #         **{msg_title}**

#     #         **演员:** {msg_actor_name}
#     #         **评分:** {score}
#     #         **下载链接:** `{magnet}`
#     #         **发布链接:** [点击查看详情]({pub_url})
#     #             """
#     # print(message)
