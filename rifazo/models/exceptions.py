# -*- coding: utf-8 -*-


class RifazoApiError(Exception):
    """Error de negocio que la API devuelve tal cual a la app.

    `code` es estable (la app decide qué mostrar según él), `message` es un
    texto listo para mostrar y `extra` viaja en el JSON (ej. los números que
    ya se llevó otro)."""

    def __init__(self, code, message, status=400, **extra):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.extra = extra

    def to_dict(self):
        return dict(self.extra, error=self.code, message=self.message)
