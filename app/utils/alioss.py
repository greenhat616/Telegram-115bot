from typing import Any

import alibabacloud_oss_v2 as oss


def upload_file_to_oss(**kwargs: Any) -> bool:
    """
    上传文件到阿里云OSS
    :param bucket: 桶名称
    :param key: 对象名称（在OSS中的路径）
    :param file_path: 本地文件路径
    :param access_key_id: 阿里云Access Key ID
    :param access_key_secret: 阿里云Access Key Secret
    :param security_token: STS临时凭证token
    :param region: 区域信息
    :param endpoint: 自定义endpoint
    :param callback: 回调参数
    """
    file_path = kwargs.get("file_path", "")
    region = kwargs.get("region", "cn-shenzhen")  # 默认深圳区域
    bucket = kwargs.get("bucket", "")
    endpoint = kwargs.get("endpoint", "")
    key = kwargs.get("key", "")
    access_key_id = kwargs.get("access_key_id", "")
    access_key_secret = kwargs.get("access_key_secret", "")
    security_token = kwargs.get("security_token", "")
    callback = kwargs.get("callback", None)
    callback_var = kwargs.get("callback_var", None)
    try:
        # 直接使用StaticCredentialsProvider，不需要先创建Credentials对象
        credentials_provider = oss.credentials.StaticCredentialsProvider(
            access_key_id=access_key_id,
            access_key_secret=access_key_secret,
            security_token=security_token,
        )
        # 加载SDK的默认配置，并设置凭证提供者
        cfg = oss.config.load_default()
        cfg.credentials_provider = credentials_provider

        # 设置配置中的区域信息
        cfg.region = region

        # 如果提供了endpoint参数，则设置配置中的endpoint
        if endpoint is not None:
            cfg.endpoint = endpoint

        # 使用配置好的信息创建OSS客户端
        client = oss.Client(cfg)

        # 执行上传对象的请求，直接从文件上传
        # 指定存储空间名称、对象名称和本地文件路径
        result = client.put_object_from_file(
            oss.PutObjectRequest(
                bucket=bucket,  # 存储空间名称
                key=key,  # 对象名称
                callback=callback,  # 回调参数
                callback_var=callback_var,
            ),
            file_path,
        )
        if result.status_code == 200:
            return True
        else:
            return False
    except oss.exceptions.BaseError as e:
        return False
