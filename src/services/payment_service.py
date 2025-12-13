from __future__ import annotations

import hashlib
import urllib.parse
from typing import Optional
import httpx


class SharkPaymentService:
    """鲨鱼支付服务"""
    
    def __init__(self, merchant_id: str, sign_key: str, api_base_url: str):
        self.merchant_id = merchant_id
        self.sign_key = sign_key
        self.api_base_url = api_base_url.rstrip('/')
    
    def generate_sign(self, data: dict) -> str:
        """生成签名
        
        规则：所有请求参数去除空值后按照ASCII码的升序进行排序，
        按照key1=value1&key2=value2进行组合，最后加上商户秘钥（&key=商户秘钥），进行md5运算，结果转为小写
        """
        # 去除空值
        filtered_data = {k: v for k, v in data.items() if v is not None and v != ''}
        
        # 按照ASCII码升序排序
        sorted_data = dict(sorted(filtered_data.items()))
        
        # 组合成 key1=value1&key2=value2 格式
        query_string = urllib.parse.urlencode(sorted_data)
        
        # 参数无需进行urlencode，还原一下
        query_string = urllib.parse.unquote(query_string)
        
        # 加上商户秘钥
        sign_string = f"{query_string}&key={self.sign_key}"
        
        # MD5运算并转为小写
        sign = hashlib.md5(sign_string.encode('utf-8')).hexdigest().lower()
        
        return sign
    
    def verify_sign(self, data: dict) -> bool:
        """验证签名"""
        received_sign = data.pop('sign', '')
        if not received_sign:
            return False
        
        calculated_sign = self.generate_sign(data)
        return received_sign.lower() == calculated_sign.lower()
    
    async def create_order(
        self,
        order_id: str,
        order_amount: str,
        notify_url: str,
        channel_type: Optional[str] = None,
        return_url: Optional[str] = None,
        payer_ip: Optional[str] = None,
        payer_id: Optional[str] = None,
        order_title: Optional[str] = None,
        order_body: Optional[str] = None,
        is_form: int = 2,  # 1=表单跳转, 2=返回JSON
    ) -> dict:
        """创建订单
        
        Returns:
            {
                "code": 200,
                "msg": "下单成功!",
                "data": {"payUrl": "http://www.baidu.com"}
            }
        """
        params = {
            "merchantId": self.merchant_id,
            "orderId": order_id,
            "orderAmount": order_amount,
            "notifyUrl": notify_url,
            "isForm": str(is_form),
        }
        
        # channelType 是必填参数，必须传递且不能为空
        # 如果未配置，抛出异常要求用户配置
        if not channel_type or not channel_type.strip():
            raise ValueError("channelType 参数不可为空，请在支付配置中设置通道类型")
        
        params["channelType"] = channel_type.strip()
        if return_url:
            params["returnUrl"] = return_url
        if payer_ip:
            params["payer_ip"] = payer_ip
        if payer_id:
            params["payer_id"] = payer_id
        if order_title:
            params["order_title"] = order_title
        if order_body:
            params["order_body"] = order_body
        
        # 生成签名
        params["sign"] = self.generate_sign(params)
        
        # 发送请求
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.api_base_url}/api/newOrder",
                data=params,
            )
            response.raise_for_status()
            return response.json()
    
    async def query_order(self, order_id: str) -> dict:
        """查询订单
        
        Returns:
            {
                "code": 200,
                "msg": "查询成功",
                "data": {
                    "merchantId": "10086",
                    "orderId": "202021231231231",
                    "status": "paid",
                    "msg": "已支付",
                    "sign": "598bcf4b666e4f413d10a77cf78e2cfb"
                }
            }
        """
        params = {
            "merchantId": self.merchant_id,
            "orderId": order_id,
        }
        
        # 生成签名
        params["sign"] = self.generate_sign(params)
        
        # 发送请求
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.api_base_url}/api/queryOrderV2",
                data=params,
            )
            response.raise_for_status()
            return response.json()

