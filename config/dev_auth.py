from rest_framework.authentication import SessionAuthentication


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """开发用：跳过 CSRF 校验的 SessionAuthentication。

    DRF 的 SessionAuthentication.enforce_csrf() 独立于 Django
    CsrfViewMiddleware 执行，注释中间件无法绕过。此子类覆盖
    enforce_csrf 为空操作，让 REST Client 等工具可以正常测试。

    仅在 DEBUG=True 时启用，生产环境应使用标准 SessionAuthentication。
    """

    def enforce_csrf(self, request):
        return
