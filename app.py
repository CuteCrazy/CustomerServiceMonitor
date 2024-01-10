import datetime
from bs4 import BeautifulSoup
import requests
import os
import time
from flask import Flask, request, abort

import uuid
import mysql.connector

from openai import OpenAI

from linebot.v3 import (
    WebhookHandler
)

from linebot.v3.exceptions import (
    InvalidSignatureError
)

from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage
)

from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent
)

app = Flask(__name__)

# Channel Access Token
channelAccessToken = 'Nh5I28S6YL+XEr3hWPH/hOicu19TCl2YDjjMXommX2bWtyNhi4MxJFlBItNK3KlRjjSaeSklwBQuImKlVTbNRoYUhao7Svrwi1qrI27pbSe+laziGnX+8eSwJhkOsdSPxF3tIpOacgQsvlbaVsadngdB04t89/1O/w1cDnyilFU='
# Channel Secret
channelSecret = '1c1ed7ad18b8bbc1b0c0c34aa0a0fdcc'

configuration = Configuration(access_token=channelAccessToken)
handler = WebhookHandler(channelSecret)

# 建立MySQL連線
dbConn = mysql.connector.connect(
    host='220.130.142.139', # 連線主機名稱
    user='root',            # 登入帳號
    password='P@int2018',   # 登入密碼
    database="pointcenter"  # 使用資料庫
)
dbCursor = dbConn.cursor()


openAIClient = OpenAI(api_key="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")


# 監聽所有來自 /callback 的 Post Request
@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.info("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)

    return 'OK'


# 處理訊息
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)

        userMessage = event.message.text
        print(f"user Message: {userMessage}")

        userId = event.source.user_id
        print(f"User ID: {userId}")

        profile = line_bot_api.get_profile(userId)
        userName = profile.display_name

        # Generate pirority from GPT
        _pirority = -1

        completion = openAIClient.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "I classify customer feedback into five categories:\r\n" +
                                    "Urgent and Critical:This is the highest priority issue that requires immediate action. It may include system crashes, security vulnerabilities, significant data loss, etc. These issues could lead to severe damage to the customer's business and reputation.\r\n" +
                                    "Urgent but Less Critical:While not as severe as the first category, these issues still require prompt resolution. Examples include certain features not working properly, system slowdowns, anomalies in dashboard reports, etc.\r\n" +
                                    "Critical but Less Urgent:Issues in this category may have some impact on the business but don't require immediate attention. This could involve improvements to important features, enhancing security, performance optimization, etc. These can be addressed in future version updates or planned cycles.\r\n" +
                                    "General Issues:These problems have a relatively minor impact on the business and can be resolved within the normal support cycle. This includes general usage issues, feature inquiries, operational guidance, etc.\r\n" +
                                    "Non-Urgent and Non-Critical:This is the lowest priority level, and these issues can be addressed at an appropriate time. This may include chit-chat, suggestions, improvement feedback, or additional features that are not time-sensitive.\r\n" +
                                    "Next, I will provide customer feedback. Just give me the classification labels, no need to explain."},
                {"role": "user", "content": userMessage}
            ]
        )
        
        gptResponse = completion.choices[0].message.content
        print(f"GPT Response: {gptResponse}")

        if gptResponse.__contains__("Urgent and Critical"):
            _pirority = 0
        elif gptResponse.__contains__("Urgent but Less Critical"):
            _pirority = 1
        elif gptResponse.__contains__("Critical but Less Urgent"):
            _pirority = 2
        elif gptResponse.__contains__("General Issues"):
            _pirority = 3
        elif gptResponse.__contains__("Non-Urgent and Non-Critical"):
            _pirority = 4
        print(f"GPT Response match pirority: {_pirority}")

        try:
            sql = "INSERT INTO wiselog (msg_key, pirority, company, report_user_name, product, msg_log, msg_time) VALUES (%s, %s, %s, %s, %s, %s, %s)"
            val = (str(uuid.uuid4()), _pirority, "", userName, "", userMessage, datetime.datetime.now().strftime('%Y%m%d%H%M%S') + "000")
            dbCursor.execute(sql, val)
            dbConn.commit()
        except Exception as e:
            print(f"Insert SQL Fail... {e}")

        replyMsg = f"{userMessage} -> {_pirority} - {gptResponse}"
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=replyMsg)]
            )
        )

        print(f"-- End --")

        # if msg == "pincode":
        #     pin = get_pin_code()
        #     line_bot_api.reply_message(event.reply_token, TextSendMessage(text = pin))
        # else:
        #     # line_bot_api.reply_message(event.reply_token, TextSendMessage(text = '目前只支援 pincode 查詢!'))
        #     # line_bot_api.reply_message(event.reply_token, TextSendMessage(text=userId))
        #     profile = line_bot_api.get_profile(userId)
        #     userName = profile.display_name
        #     line_bot_api.reply_message(event.reply_token, TextSendMessage(text="reply Hello " + userName + " your id: " + userId))

        #     # crazyID = "Ud106de7d9e9b720e4cbabfb8b2313b2f"
        #     line_bot_api.push_message(userId, TextSendMessage(text=userName + " is finding you"))
        #     line_bot_api.push_message(userId, TextSendMessage(text=userName + " say " + msg))

        #     # line_bot_api.push_message(crazyID, TextSendMessage(text="2020/03/27 11:48:37 RichTV BLUR"))
        
        


if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)


