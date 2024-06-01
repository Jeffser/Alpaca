document.oncontextmenu = new Function("return false;")
window.ondragstart = function () { return false }

document.addEventListener('DOMContentLoaded', function () {
    const header = document.getElementById('header');
    const targetElement = document.getElementById('targetElement');

    window.addEventListener('scroll', function () {
        const targetPosition = targetElement.getBoundingClientRect().top;
        const headerHeight = header.offsetHeight;

        if (targetPosition < headerHeight) {
            header.classList.add('show');
        } else {
            header.classList.remove('show');
        }
    });
});

document.addEventListener( 'DOMContentLoaded', function () {
    new Splide( '#image-carousel',{
        type:'loop',
    } ).mount();
  } );  