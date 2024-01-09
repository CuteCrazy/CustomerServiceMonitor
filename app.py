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
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "我把告警分成四類\r\n" +
                                    "緊急警報：告警規則對應資源發生緊急故障，影響業務視為緊急警報。\r\n" +
                                    "重要警告：警報規則對應資源有影響業務的問題，此問題相對較嚴重，有可能阻礙資源的正常使用。\r\n" +
                                    "次要警告：警告規則對應資源有相對較不嚴重點問題，此問題不會阻礙資源的正常使用。\r\n" +
                                    "提示警告：告警規則對應資源有潛在的錯誤可能影響到業務。\r\n" +
                                    "接下來會給你告警分類，只需要給我分類標籤，不需要解釋。"},
                {"role": "user", "content": userMessage}
            ]
        )
        
        gptResponse = completion.choices[0].message.content
        print(f"GPT Response: {gptResponse}")

        if gptResponse.__contains__("緊急警報"):
            _pirority = 0
        elif gptResponse.__contains__("重要警告"):
            _pirority = 1
        elif gptResponse.__contains__("次要警告"):
            _pirority = 2
        elif gptResponse.__contains__("提示警告"):
            _pirority = 3
        print(f"GPT Response match pirority: {_pirority}")

        try:
            sql = "INSERT INTO wiselog (msg_key, pirority, company, report_user_name, product, msg_log, msg_time) VALUES (%s, %s, %s, %s, %s, %s, %s)"
            val = (str(uuid.uuid4()), _pirority, "", userName, "", userMessage, time.strftime('%Y%m%d%H%M%S'))
            dbCursor.execute(sql, val)
            dbConn.commit()
        except Exception as e:
            print(f"Insert SQL Fail... {e}")

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
        
        # line_bot_api.reply_message_with_http_info(
        #     ReplyMessageRequest(
        #         reply_token=event.reply_token,
        #         messages=[TextMessage(text=event.message.text)]
        #     )
        # )


if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)


