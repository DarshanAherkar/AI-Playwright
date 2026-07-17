const tabs = document.querySelectorAll('.tab');
const forms = document.querySelectorAll('.auth-form');

for (const tab of tabs) {
  tab.addEventListener('click', () => {
    const target = tab.dataset.form;

    tabs.forEach((btn) => btn.classList.remove('active'));
    forms.forEach((form) => form.classList.remove('active'));

    tab.classList.add('active');
    document.getElementById(`${target}Form`).classList.add('active');
  });
}

for (const form of forms) {
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    const title = form.querySelector('h2').textContent;
    alert(`${title} successful!`);
    form.reset();

    if (form.id === 'loginForm') {
      window.location.href = '/dashboard.html';
    }
  });
}

const goToCartButton = document.getElementById('goToCart');
if (goToCartButton) {
  goToCartButton.addEventListener('click', () => {
    window.location.href = '/cart.html';
  });
}

const checkoutButton = document.getElementById('checkout');
if (checkoutButton) {
  checkoutButton.addEventListener('click', () => {
    window.location.href = '/payment.html';
  });
}

const paymentForm = document.getElementById('paymentForm');
if (paymentForm) {
  paymentForm.addEventListener('submit', (event) => {
    event.preventDefault();
    alert('Payment successful!');
    paymentForm.reset();
  });
}
