(function () {
  function buildOverlay() {
    var overlay = document.createElement("div");
    overlay.className = "lightbox";
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-modal", "true");
    overlay.innerHTML = '<button class="lightbox-close" aria-label="Close">&times;</button><img alt="" />';
    document.body.appendChild(overlay);
    return overlay;
  }

  function close(overlay) {
    overlay.classList.remove("is-open");
    var img = overlay.querySelector("img");
    if (img) img.src = "";
    document.body.style.overflow = "";
  }

  function open(overlay, src, alt) {
    var img = overlay.querySelector("img");
    img.src = src;
    img.alt = alt || "";
    overlay.classList.add("is-open");
    document.body.style.overflow = "hidden";
  }

  document.addEventListener("DOMContentLoaded", function () {
    var overlay = buildOverlay();
    var triggers = document.querySelectorAll(".lightbox-trigger");

    triggers.forEach(function (el) {
      el.addEventListener("click", function (e) {
        e.preventDefault();
        var img = el.querySelector("img");
        var src = el.getAttribute("href") || (img && img.src);
        var alt = img && img.alt;
        if (src) open(overlay, src, alt);
      });
    });

    overlay.addEventListener("click", function (e) {
      if (e.target === overlay || e.target.classList.contains("lightbox-close")) {
        close(overlay);
      }
    });

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && overlay.classList.contains("is-open")) {
        close(overlay);
      }
    });
  });
})();
