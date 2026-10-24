/* STRIDE — layout injection, carrinho (localStorage) e renderização */

const CART_KEY = "stride_cart_v1";

const ICON_BAG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4Z"/><path d="M3 6h18"/><path d="M16 10a4 4 0 0 1-8 0"/></svg>';
const ICON_HEART = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.6l-1-1a5.5 5.5 0 0 0-7.8 7.8l1 1L12 21l7.8-7.8 1-1a5.5 5.5 0 0 0 0-7.8Z"/></svg>';

/* ---------- Carrinho ---------- */
function getCart() {
  try {
    return JSON.parse(localStorage.getItem(CART_KEY) || "[]");
  } catch (e) {
    return [];
  }
}

function saveCart(cart) {
  try {
    localStorage.setItem(CART_KEY, JSON.stringify(cart));
  } catch (e) {
    /* localStorage indisponível (ex.: aba privada) — segue sem persistir */
  }
}

function addToCart(id, size, color, qty) {
  const cart = getCart();
  const existing = cart.find((i) => i.id === id && i.size === size && i.color === color);
  if (existing) {
    existing.qty += qty;
  } else {
    cart.push({ id, size, color, qty });
  }
  saveCart(cart);
  renderCartDrawer();
  updateCartCount();
}

function changeQty(idx, delta) {
  const cart = getCart();
  if (!cart[idx]) return;
  cart[idx].qty += delta;
  if (cart[idx].qty < 1) cart.splice(idx, 1);
  saveCart(cart);
  renderCartDrawer();
  updateCartCount();
}

function removeFromCart(idx) {
  const cart = getCart();
  cart.splice(idx, 1);
  saveCart(cart);
  renderCartDrawer();
  updateCartCount();
}

function cartTotal() {
  return getCart().reduce((sum, item) => {
    const p = getProductById(item.id);
    return sum + (p ? p.price * item.qty : 0);
  }, 0);
}

function updateCartCount() {
  const el = document.getElementById("cartCount");
  if (!el) return;
  el.textContent = getCart().reduce((sum, i) => sum + i.qty, 0);
}

function renderCartDrawer() {
  const itemsEl = document.getElementById("cartItems");
  const footEl = document.getElementById("cartFoot");
  if (!itemsEl) return;
  const cart = getCart();

  if (cart.length === 0) {
    itemsEl.innerHTML =
      '<div class="cart-empty">Sua sacola está vazia.<br><br>' +
      '<a href="loja.html" class="btn btn--outline">Ver Loja</a></div>';
    if (footEl) footEl.style.display = "none";
    return;
  }

  if (footEl) footEl.style.display = "block";

  itemsEl.innerHTML = cart
    .map((item, idx) => {
      const p = getProductById(item.id);
      if (!p) return "";
      return (
        '<div class="cart-item">' +
        '<img src="' + productImage(p.seed, 100, 124) + '" alt="' + p.name + '">' +
        '<div class="cart-item__info">' +
        '<div class="cart-item__name">' + p.name + "</div>" +
        '<div class="cart-item__meta">Tam ' + item.size + " · " + item.color + "</div>" +
        '<div class="cart-item__row">' +
        '<div class="qty-stepper">' +
        '<button type="button" data-qty="-1" data-idx="' + idx + '" aria-label="Diminuir">−</button>' +
        "<span>" + item.qty + "</span>" +
        '<button type="button" data-qty="1" data-idx="' + idx + '" aria-label="Aumentar">+</button>' +
        "</div>" +
        "<strong>" + formatPrice(p.price * item.qty) + "</strong>" +
        "</div>" +
        '<button class="cart-item__remove" type="button" data-remove="' + idx + '">Remover</button>' +
        "</div></div>"
      );
    })
    .join("");

  const subtotalEl = document.getElementById("cartSubtotal");
  if (subtotalEl) subtotalEl.textContent = formatPrice(cartTotal());
}

function openCart() {
  const drawer = document.getElementById("cartDrawer");
  const overlay = document.getElementById("overlay");
  if (!drawer || !overlay) return;
  drawer.classList.add("open");
  overlay.classList.add("open");
  document.body.style.overflow = "hidden";
}

function closeCart() {
  const drawer = document.getElementById("cartDrawer");
  const overlay = document.getElementById("overlay");
  if (!drawer || !overlay) return;
  drawer.classList.remove("open");
  overlay.classList.remove("open");
  document.body.style.overflow = "";
}

function toggleMobileMenu() {
  const nav = document.getElementById("mobileNav");
  if (nav) nav.classList.toggle("open");
}

let toastTimer;
function showToast(msg) {
  const el = document.getElementById("toast");
  if (!el) return;
  el.textContent = msg;
  el.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("show"), 2600);
}

/* ---------- Cards / grids ---------- */
function renderProductCard(p) {
  const cat = getCategoryBySlug(p.cat);
  const badge = p.badge ? '<span class="product-card__badge">' + p.badge + "</span>" : "";
  return (
    '<div class="product-card">' +
    '<div class="product-card__media">' +
    '<a href="produto.html?id=' + p.id + '" aria-label="' + p.name + '">' +
    '<img src="' + productImage(p.seed, 500, 625) + '" alt="' + p.name + '" loading="lazy">' +
    "</a>" +
    badge +
    '<button class="btn btn--light btn--block product-card__quick" type="button" data-quick-add="' + p.id + '">+ Adicionar</button>' +
    "</div>" +
    '<a href="produto.html?id=' + p.id + '" class="product-card__body">' +
    '<div class="product-card__cat">' + (cat ? cat.name : "") + "</div>" +
    '<div class="product-card__name">' + p.name + "</div>" +
    '<div class="product-card__price">' + formatPrice(p.price) + "</div>" +
    "</a></div>"
  );
}

function renderProductGrid(container, list) {
  if (!container) return;
  if (!list.length) {
    container.innerHTML = '<div class="empty-state">Nenhum produto encontrado nessa categoria.</div>';
    return;
  }
  container.innerHTML = list.map(renderProductCard).join("");
}

function renderCategoryGrid(container) {
  if (!container) return;
  container.innerHTML = CATEGORIES.map((c) => {
    const count = PRODUCTS.filter((p) => p.cat === c.slug).length;
    return (
      '<a class="cat-card" href="loja.html?cat=' + c.slug + '">' +
      '<img src="' + productImage(c.image, 400, 520) + '" alt="' + c.name + '" loading="lazy">' +
      '<div class="cat-card__label">' + c.name + "<small>" + count + " itens</small></div>" +
      "</a>"
    );
  }).join("");
}

/* ---------- Layout (header / footer / carrinho) ---------- */
function headerHTML(active) {
  const navLink = (href, key, label) =>
    '<a href="' + href + '" class="' + (active === key ? "active" : "") + '">' + label + "</a>";

  const mobileLinks =
    '<li><a href="index.html">Início</a></li>' +
    '<li><a href="loja.html">Loja</a></li>' +
    CATEGORIES.map((c) => '<li><a href="loja.html?cat=' + c.slug + '">' + c.name + "</a></li>").join("") +
    '<li><a href="sobre.html">Sobre</a></li>';

  return (
    '<header class="site-header"><div class="container site-header__inner">' +
    '<a href="index.html" class="logo">STR<span>IDE</span></a>' +
    '<nav class="nav-desktop">' +
    navLink("index.html", "home", "Início") +
    navLink("loja.html", "loja", "Loja") +
    navLink("sobre.html", "sobre", "Sobre") +
    "</nav>" +
    '<div class="header-actions">' +
    '<button class="icon-btn" id="cartToggle" type="button" aria-label="Abrir sacola">' +
    ICON_BAG +
    '<span class="cart-count" id="cartCount">0</span>' +
    "</button>" +
    '<button class="menu-toggle" id="menuToggle" type="button" aria-label="Abrir menu">' +
    "<span></span><span></span><span></span>" +
    "</button>" +
    "</div></div></header>" +
    '<div class="mobile-nav" id="mobileNav"><ul>' + mobileLinks + "</ul></div>"
  );
}

function footerHTML() {
  const catLinks = CATEGORIES.map((c) => '<li><a href="loja.html?cat=' + c.slug + '">' + c.name + "</a></li>").join("");
  return (
    '<footer class="site-footer"><div class="container">' +
    '<div class="footer-grid">' +
    '<div class="footer-brand">' +
    '<a href="index.html" class="logo">STR<span>IDE</span></a>' +
    "<p>Roupas e calçados feitos pra quem não para. Performance, atitude e streetwear em cada peça.</p>" +
    "</div>" +
    "<div><h4>Categorias</h4><ul>" + catLinks + "</ul></div>" +
    '<div><h4>Institucional</h4><ul>' +
    '<li><a href="sobre.html">Sobre a STRIDE</a></li>' +
    '<li><a href="#">Trabalhe Conosco</a></li>' +
    '<li><a href="#">Sustentabilidade</a></li>' +
    '<li><a href="#">Lojas Físicas</a></li>' +
    "</ul></div>" +
    '<div><h4>Atendimento</h4><ul>' +
    '<li><a href="#">Central de Ajuda</a></li>' +
    '<li><a href="#">Trocas e Devoluções</a></li>' +
    '<li><a href="#">Guia de Tamanhos</a></li>' +
    '<li><a href="#">Rastrear Pedido</a></li>' +
    "</ul></div>" +
    "</div>" +
    '<div class="footer-bottom">' +
    "<span>© 2026 STRIDE. Todos os direitos reservados.</span>" +
    "<span>Site de demonstração — nenhum pedido real é processado.</span>" +
    "</div></div></footer>"
  );
}

function cartDrawerHTML() {
  return (
    '<div class="overlay" id="overlay"></div>' +
    '<aside class="cart-drawer" id="cartDrawer">' +
    '<div class="cart-drawer__head"><h3>Sua Sacola</h3>' +
    '<button class="cart-drawer__close" id="cartClose" type="button" aria-label="Fechar">×</button></div>' +
    '<div class="cart-drawer__items" id="cartItems"></div>' +
    '<div class="cart-drawer__foot" id="cartFoot">' +
    '<div class="cart-subtotal"><span>Subtotal</span><span id="cartSubtotal">R$ 0,00</span></div>' +
    '<button class="btn btn--primary btn--block" id="checkoutBtn" type="button">Finalizar Compra</button>' +
    "</div></aside>" +
    '<div class="toast" id="toast"></div>'
  );
}

function injectLayout(activePage) {
  const headerRoot = document.getElementById("header-root");
  const footerRoot = document.getElementById("footer-root");
  const cartRoot = document.getElementById("cart-root");
  if (headerRoot) headerRoot.innerHTML = headerHTML(activePage);
  if (footerRoot) footerRoot.innerHTML = footerHTML();
  if (cartRoot) cartRoot.innerHTML = cartDrawerHTML();
  updateCartCount();
  renderCartDrawer();

  window.addEventListener("resize", () => {
    if (window.innerWidth > 900) {
      const nav = document.getElementById("mobileNav");
      if (nav) nav.classList.remove("open");
    }
  });
}

/* ---------- Eventos globais (delegação) ---------- */
document.addEventListener("click", (e) => {
  const qtyBtn = e.target.closest("[data-qty]");
  if (qtyBtn) {
    changeQty(Number(qtyBtn.dataset.idx), Number(qtyBtn.dataset.qty));
    return;
  }
  const removeBtn = e.target.closest("[data-remove]");
  if (removeBtn) {
    removeFromCart(Number(removeBtn.dataset.remove));
    return;
  }
  const quickAdd = e.target.closest("[data-quick-add]");
  if (quickAdd) {
    const p = getProductById(Number(quickAdd.dataset.quickAdd));
    if (p) {
      addToCart(p.id, p.sizes[0], p.colors[0].name, 1);
      openCart();
    }
    return;
  }
  if (e.target.closest("#cartToggle")) {
    openCart();
    return;
  }
  if (e.target.closest("#cartClose") || e.target.id === "overlay") {
    closeCart();
    return;
  }
  if (e.target.closest("#menuToggle")) {
    toggleMobileMenu();
    return;
  }
  if (e.target.closest("#checkoutBtn")) {
    showToast("Compra de demonstração — conecte um checkout real aqui.");
    return;
  }
});
