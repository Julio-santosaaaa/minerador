# STRIDE — site de ecommerce (demo)

Site estático de vitrine para uma loja de roupas/streetwear fictícia, com estética
esportiva bold (preto/branco/volt, tipografia condensada) inspirada no visual de
marcas como Nike e Insider — sem usar nome, logo ou produtos reais dessas marcas.

Sem build, sem backend: HTML + CSS + JS puro. Carrinho e favoritos são só
`localStorage`, o botão "Finalizar Compra" mostra um aviso de demonstração.

## Estrutura

- `index.html` — Home (hero, categorias, destaques, newsletter)
- `loja.html` — Catálogo com filtro por categoria (`?cat=tenis`, etc.)
- `produto.html` — Detalhe do produto (`?id=1`), galeria, tamanho/cor, relacionados
- `sobre.html` — História, valores e números da marca
- `css/style.css` — Design system (cores, tipografia, componentes)
- `js/products.js` — Catálogo de produtos e categorias (dados estáticos)
- `js/main.js` — Header/footer/carrinho injetados via JS + lógica de carrinho

## Rodar localmente

Abrir `index.html` direto no navegador já funciona, mas o carrinho persiste
melhor servindo a pasta (evita restrições de `localStorage` em `file://`):

```
npx http-server loja -p 8080
# ou
python3 -m http.server 8080 --directory loja
```

## Fotos

As imagens usam [Picsum](https://picsum.photos) (`https://picsum.photos/seed/<seed>/<w>/<h>`)
como placeholder — todas geradas pela função `productImage()` em `js/products.js`.
Pra trocar por fotos reais dos produtos, basta apontar o `seed` de cada item (ou a
própria função) pra URLs das suas imagens.
