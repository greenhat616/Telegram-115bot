from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from app import init
from app.utils.ptb_helpers import require_message, require_query, require_chat, require_user, require_user_data
import datetime
import threading


async def crawl_sehua(update: Update, context: ContextTypes.DEFAULT_TYPE):
    usr_id = require_user(update).id
    if not init.check_user(usr_id):
        await require_message(update).reply_text("⚠️ 对不起，您无权使用115机器人！")
        return
    yesterday = datetime.datetime.now() - datetime.timedelta(days=1)
    date = yesterday.strftime("%Y-%m-%d")
    require_user_data(context)["date"] = date  # 默认使用昨日日期
    init.logger.info("涩花默认爬取昨日数据")
    
    if init.CRAWL_SEHUA_STATUS == 1:
        await require_message(update).reply_text("⚠️ 涩花爬取任务正在进行中，请稍后再试！")
        return
    else:
        init.CRAWL_SEHUA_STATUS = 1
        await require_message(update).reply_text(f"🕷️ 开始爬取涩花数据，日期: {require_user_data(context)['date']}，爬取完成后会发送通知，请稍后...")
        from app.core.sehua_spider import sehua_spider_by_date
        thread = threading.Thread(target=sehua_spider_by_date, args=(require_user_data(context)['date'],))
        thread.start()
        return

async def crawl_jav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    usr_id = require_user(update).id
    if not init.check_user(usr_id):
        await require_message(update).reply_text("⚠️ 对不起，您无权使用115机器人！")
        return

    if context.args:
        date = " ".join(context.args)
        date_obj = datetime.datetime.strptime(date, "%Y%m%d")
        formatted_date = date_obj.strftime("%Y-%m-%d")
        require_user_data(context)["date"] = formatted_date  # 将用户参数存储起来
    else:
        yesterday = datetime.datetime.now() - datetime.timedelta(days=1)
        date = yesterday.strftime("%Y-%m-%d")
        require_user_data(context)["date"] = date  # 默认使用昨日日期
        init.logger.info("用户没有输入日期参数，默认爬取昨日数据")
        
    if init.CRAWL_JAV_STATUS == 1:
        await require_message(update).reply_text("⚠️ javbee爬取任务正在进行中，请稍后再试！")
        return
    else:
        init.CRAWL_JAV_STATUS = 1
        await require_message(update).reply_text(f"🕷️ 开始爬取javbee数据，日期: {require_user_data(context)['date']}，爬取完成后会发送通知，请稍后...")
        from app.core.av_daily_update import crawl_javbee_by_date
        thread = threading.Thread(target=crawl_javbee_by_date, args=(require_user_data(context)['date'],))
        thread.start()
        return


def register_crawl_handlers(application):
    """crawl处理器注册函数"""
    crawl_sehua_handler = CommandHandler('csh', crawl_sehua)
    application.add_handler(crawl_sehua_handler)
    crawl_jav_handler = CommandHandler('cjav', crawl_jav)
    application.add_handler(crawl_jav_handler)
    init.logger.info("✅ Crawl处理器已注册")