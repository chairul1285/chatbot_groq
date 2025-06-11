// scroll top btn
let scrollTop = document.querySelector('.scroll-top-btn');

window.addEventListener('scroll', function () {
	if (window.pageYOffset > 70) {
		scrollTop.classList.add('active');
	} else {
		scrollTop.classList.remove('active');
	}
});

// menu toggle bar
let navToggler = document.querySelector('.nav-toggler');
let menuItems = document.querySelector('.menu-items');

let navList = document.querySelectorAll('.menu-items > li > a');

navToggler.addEventListener('click', function () {
	navToggler.classList.toggle('active');
	menuItems.classList.toggle('show');

	for (let i = 0; i < navList.length; i++) {
		navList[i].addEventListener('click', function () {
			navToggler.classList.remove('active');
			menuItems.classList.remove('show');
		});
	}
});

// aos animation
AOS.init({
	duration: 1000
});