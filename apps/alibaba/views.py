#coding:utf-8


from base import BaseHandler

from apps.alibaba.alibabaAPI import *
from apps.database.databaseCase import *
import json
import datetime
import re
import tornado.web
import random

import tornado.gen
import tornado.httpclient
from tornado.httpclient import HTTPRequest
import urllib

apiServer = 'http://127.0.0.1:5000'


class PurchaseListHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):

        homePath = self.getHome()

        AUTHOR_MOUDLE = 'ViewPurchase'

        user = self.current_user
        role = self.get_secure_cookie("role") if self.get_secure_cookie("role") else 'None'

        mongo = MongoCase()
        mongo.connect()
        client = mongo.client

        db = client.woderp

        account = db.user.find_one({'account': user})

        authority = self.getAuthority(account, AUTHOR_MOUDLE)

        if authority['Allow']:

            pageSize = 50

            status = self.get_argument('status','')
            wd = self.get_argument('wd','')
            key = self.get_argument('key','')

            try:
                page = int(self.get_argument('page',1))
            except:
                page = 1

            option = {}

            if authority['role'] == 'Supper':
                appList = db.appList.find({'platform': '1688'})
            else:
                appList = db.appList.find({'platform': '1688','appKey':{'$in':authority['authority']['purchaseAccount']}})

            if status != '':
                option['status'] = status

            if key != '':
                option['appKey'] = key
            elif authority['role'] != 'Supper':
                option['appKey'] = {'$in':authority['authority']['purchaseAccount']}

            statusList = db.purchaseList.aggregate(
                [{'$match': option}, {'$group': {'_id': "$status", 'orderCount': {'$sum': 1}}}])

            sL = []
            for s in statusList:
                if s['_id']:
                    stxt = ''
                    if s['_id'] == 'waitbuyerpay':
                        stxt += '等待买家付款'
                    elif s['_id'] == 'waitsellersend':
                        stxt += '等待卖家发货'
                    elif s['_id'] == 'waitbuyerreceive':
                        stxt += '等待买家收货'
                    elif s['_id'] == 'success':
                        stxt += '交易完成'
                    elif s['_id'] == 'cancel':
                        stxt += '交易取消'
                    sL.append({'status': s['_id'], 'orderCount': s['orderCount'], 'statusTxt': stxt})

            if wd != '':
                words = re.compile(wd)

                filerList = []
                filerList.append({'orderEntries.productName':words})
                filerList.append({'toFullName':words})
                filerList.append({'toMobile':words})
                filerList.append({'buyerAccount':words})
                filerList.append({'sellerCompanyName':words})
                filerList.append({'logistics.toContact':words})
                filerList.append({'logistics.logisticsBillNo':words})
                try:
                    filerList.append({'id':int(wd)})
                except:
                    pass

                option['$or'] = filerList


            totalCount = db.purchaseList.find(option).count()

            purchaseList = db.purchaseList.find(option).sort("gmtCreate",-1).limit(pageSize).skip((page-1)*pageSize)

            p = divmod(totalCount,pageSize)

            pageInfo = dict()

            totalPage = p[0]
            if p[1]>0:
                totalPage += 1

            pageInfo['totalPage'] = totalPage
            pageInfo['totalCount'] = totalCount
            pageInfo['pageSize'] = pageSize
            pageInfo['pageNo'] = page
            pageInfo['pageList'] = range(1,totalPage+1)

            filterData = dict()
            filterData['status'] = status
            filterData['wd'] = wd
            filterData['key'] = key
            filterData['appList'] = appList
            filterData['statusList'] = sL

            self.render('purchase/purchase-list.html',purchaseList = purchaseList,homePath=homePath,pageInfo = pageInfo,filterData=filterData,userInfo={'account':user,'role':role,'authority':authority})

            #self.render('index.html')
        else:
            self.render('error/message.html',homePath=homePath, msg={'Msg': 'No Permission', 'Code': 400, 'Title': '无权限！', 'Link': '/'})



class CheckPurchaseHandler(BaseHandler):
    @tornado.web.asynchronous
    @tornado.gen.engine
    def get(self):

        key = self.get_argument('key','')

        orderStatus = self.get_argument('orderStatus', '')
        pageNO = self.get_argument('pageNO', '1')
        createStartTime = self.get_argument('createStartTime', '')
        createEndTime = self.get_argument('createEndTime', '')

        url = apiServer+"/purchase/api/checkPurchase?"+urllib.urlencode({'key':key,'orderStatus':orderStatus,'pageNO':pageNO,'createStartTime':createStartTime,'createEndTime':createEndTime})
        request = HTTPRequest(url=url,method="GET",follow_redirects=False,request_timeout=3000)
        client = tornado.httpclient.AsyncHTTPClient()
        response = yield tornado.gen.Task(client.fetch, request)
        result = json.loads(response.body)
        self.write(result)
        self.finish()



class CheckPurchaseInfoHandler(BaseHandler):

    def get(self):
        data = dict()
        orderId = self.get_argument('orderId', '')
        if orderId != '':

            mongo = MongoCase()
            mongo.connect()
            client = mongo.client
            db = client.woderp

            od = db.purchaseList.find_one({"id": int(orderId)})
            if od:
                app = db.appList.find_one({'memberId':od['buyerMemberId']})
                api = ALIBABA(app)
                d = api.getOrderDetail(orderId)
                result = json.loads(d)

                if result.has_key('result') and result['result']['success']:

                    orderInfo = result['result']['toReturn'][0]

                    item = dict()

                    if orderInfo.has_key('logistics'):
                        item['logistics'] = orderInfo['logistics']

                    if orderInfo.has_key('sellerCompanyName'):
                        item['sellerCompanyName'] = orderInfo['sellerCompanyName']

                    if orderInfo.has_key('sellerPhone'):
                        item['sellerPhone'] = orderInfo['sellerPhone']

                    if orderInfo.has_key('sellerMobile'):
                        item['sellerMobile'] = orderInfo['sellerMobile']

                    item['orderEntries'] = orderInfo['orderEntries']

                    try:
                        d = datetime.datetime.strptime(orderInfo['gmtModified'][:14],'%Y%m%d%H%M%S')
                        item['gmtModified'] = d.strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        pass

                    try:
                        d = datetime.datetime.strptime(orderInfo['gmtPayment'][:14],'%Y%m%d%H%M%S')
                        item['gmtPayment'] = d.strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        pass


                    item['status'] = orderInfo['status']

                    item['updateTime'] = datetime.datetime.now()


                    db.purchaseList.update({"id": int(orderId)}, {'$set': item})

                    data['success'] = True

                else:
                    data['success'] = False
                    data['msg'] = 'Update ERROR'


        else:
            data['success'] = False
            data['msg'] = 'ERROR'

        self.set_header('Content-Type', 'application/json; charset=UTF-8')
        self.write(json.dumps(data, ensure_ascii=False))


class CheckPurchaseLogistHandler(BaseHandler):

    def get(self):
        data = dict()
        ids = self.get_argument('ids', '')
        ids = ids.split(',')
        data['total'] = len(ids)
        data['successCount'] = 0
        data['errorCount'] = 0


        mongo = MongoCase()
        mongo.connect()
        client = mongo.client
        db = client.woderp

        for orderId in ids:

            od = db.purchaseList.find_one({"id": int(orderId)})

            app = db.appList.find_one({'memberId':od['buyerMemberId']})
            api = ALIBABA(app)

            d = api.getOrderDetail(orderId)
            result = json.loads(d)

            if result.has_key('result') and result['result']['success']:

                orderInfo = result['result']['toReturn'][0]

                item = dict()

                if orderInfo.has_key('logistics'):
                    item['logistics'] = orderInfo['logistics']

                if orderInfo.has_key('sellerCompanyName'):
                    item['sellerCompanyName'] = orderInfo['sellerCompanyName']

                if orderInfo.has_key('sellerPhone'):
                    item['sellerPhone'] = orderInfo['sellerPhone']

                if orderInfo.has_key('sellerMobile'):
                    item['sellerMobile'] = orderInfo['sellerMobile']

                item['orderEntries'] = orderInfo['orderEntries']

                try:
                    d = datetime.datetime.strptime(orderInfo['gmtModified'][:14],'%Y%m%d%H%M%S')
                    item['gmtModified'] = d.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    pass

                try:
                    d = datetime.datetime.strptime(orderInfo['gmtPayment'][:14],'%Y%m%d%H%M%S')
                    item['gmtPayment'] = d.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    pass


                item['status'] = orderInfo['status']

                item['updateTime'] = datetime.datetime.now()


                db.purchaseList.update({"id": int(orderId)}, {'$set': item})

                data['successCount'] += 1

            else:
                data['errorCount'] += 1


        self.write(json.dumps(data, ensure_ascii=False))



class getPurchaseInfoHandler(BaseHandler):

    def get(self):
        data = dict()
        orderId = self.get_argument('orderId', '')
        if orderId != '':

            mongo = MongoCase()
            mongo.connect()
            client = mongo.client
            db = client.woderp

            orderInfo = db.purchaseList.find_one({"id": int(orderId)})

            data['data'] = orderInfo
            data['data']['createTime'] = data['data']['createTime'].strftime('%Y-%m-%d %H:%M:%S')
            data['data']['updateTime'] = str(data['data']['updateTime'])
            data['data']['_id'] = str(data['data']['_id'])

            data['success'] = True

        else:
            data['success'] = False
            data['msg'] = 'ERROR'

        self.set_header('Content-Type', 'application/json; charset=UTF-8')
        self.write(json.dumps(data, ensure_ascii=False))



class ParseAddressHandler(BaseHandler):

    def get(self):
        data = dict()
        addressInfo = self.get_argument('addressInfo', '')
        key = self.get_argument('key', '4647725')

        data['success'] = False
        if addressInfo!= '':

            mongo = MongoCase()
            mongo.connect()
            client = mongo.client
            db = client.woderp

            app = db.appList.find_one({'platform': '1688','appKey':key})

            if app != None:
                api = ALIBABA(app)
                data['success'] = True
                data['address'] = json.loads(api.parseAddress(addressInfo))


        self.set_header('Content-Type', 'application/json; charset=UTF-8')
        self.write(json.dumps(data, ensure_ascii=False))

