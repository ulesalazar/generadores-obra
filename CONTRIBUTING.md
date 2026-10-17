# Cómo contribuir

1. Abra un *issue* describiendo el cambio, sobre todo si toca un criterio normativo
   (cite el artículo o la publicación del DOF).
2. Haga un *fork*, cree una rama y agregue pruebas.
3. Antes de enviar el *pull request*:

```bash
pip install -e ".[dev]"
ruff check . && ruff format --check .
pytest
```

Si agrega un formato de entrada, incluya un ejemplo en
`ejemplos/` y su prueba.
