// Download page logic. Reads the newest published "studio-v*" release from
// the public GitHub API and lists its installers by operating system.
// No tracking, no cookies, no third-party scripts.
(function () {
  "use strict";

  var REPO = "oasis-main/oasis-firmware";
  var RELEASES_URL = "https://github.com/" + REPO + "/releases";

  var OS = [
    { id: "macos", label: "macOS", test: /\.dmg$/i, kinds: [[/universal\.dmg$/i, "Universal (Apple silicon and Intel)"], [/aarch64\.dmg$/i, "Apple silicon"], [/x64\.dmg$/i, "Intel"], [/\.dmg$/i, "Disk image"]] },
    { id: "windows", label: "Windows", test: /(\.msi|-setup\.exe)$/i, kinds: [[/-setup\.exe$/i, "Installer (.exe)"], [/\.msi$/i, "Installer (.msi)"]] },
    { id: "linux", label: "Linux", test: /\.(AppImage|deb|rpm)$/i, kinds: [[/\.AppImage$/i, "AppImage (any distribution)"], [/\.deb$/i, "Debian / Ubuntu (.deb)"], [/\.rpm$/i, "Fedora / openSUSE (.rpm)"]] },
  ];

  function detectOs() {
    var p = (navigator.userAgentData && navigator.userAgentData.platform) || navigator.platform || navigator.userAgent || "";
    if (/mac/i.test(p)) return "macos";
    if (/win/i.test(p)) return "windows";
    if (/linux|x11/i.test(p)) return "linux";
    return null;
  }

  function kindOf(os, name) {
    for (var i = 0; i < os.kinds.length; i++) if (os.kinds[i][0].test(name)) return os.kinds[i][1];
    return "Installer";
  }

  function el(tag, attrs, text) {
    var e = document.createElement(tag);
    for (var k in attrs || {}) e.setAttribute(k, attrs[k]);
    if (text != null) e.textContent = text;
    return e;
  }

  function mb(bytes) {
    return (bytes / 1048576).toFixed(1) + " MB";
  }

  var mine = detectOs();
  var mineLabel = OS.filter(function (o) { return o.id === mine; }).map(function (o) { return o.label; })[0];

  // Overview page: name the user's OS on the main button.
  var cta = document.getElementById("cta-download");
  if (cta && mineLabel) cta.textContent = "Download for " + mineLabel;

  var target = document.getElementById("downloads");
  if (!target) return;

  function showNoRelease(reason) {
    target.innerHTML = "";
    var box = el("div", { class: "card" });
    box.appendChild(el("h3", {}, "No installer is published yet"));
    box.appendChild(el("p", {}, reason));
    var p = el("p", {});
    p.appendChild(document.createTextNode("Build from source with the steps below, or check "));
    p.appendChild(el("a", { href: RELEASES_URL }, "the releases page"));
    p.appendChild(document.createTextNode(" later."));
    box.appendChild(p);
    target.appendChild(box);
  }

  fetch("https://api.github.com/repos/" + REPO + "/releases?per_page=20", { headers: { Accept: "application/vnd.github+json" } })
    .then(function (r) {
      if (!r.ok) throw new Error("GitHub answered " + r.status);
      return r.json();
    })
    .then(function (releases) {
      var rel = releases.filter(function (r) { return !r.draft && /^studio-v/.test(r.tag_name); })[0];
      if (!rel) return showNoRelease("Oasis Studio has no published release on GitHub at this time.");

      target.innerHTML = "";
      var head = el("p", { class: "small" });
      head.appendChild(document.createTextNode("Version " + rel.tag_name.replace(/^studio-v/, "") + " · published " + new Date(rel.published_at).toLocaleDateString() + " · "));
      head.appendChild(el("a", { href: rel.html_url }, "release notes"));
      target.appendChild(head);

      // The user's OS first.
      var order = OS.slice().sort(function (a, b) { return (b.id === mine) - (a.id === mine); });
      order.forEach(function (os) {
        var assets = rel.assets.filter(function (a) { return os.test.test(a.name); });
        if (!assets.length) return;
        var block = el("div", { class: "os-block" });
        block.appendChild(el("h3", {}, os.label + (os.id === mine ? " (this computer)" : "")));
        var list = el("div", { class: "dl-list" });
        assets.forEach(function (a) {
          var row = el("div", { class: "dl-item" + (os.id === mine ? " mine" : "") });
          var info = el("div", {});
          info.appendChild(el("div", {}, kindOf(os, a.name)));
          info.appendChild(el("div", { class: "name" }, a.name + " · " + mb(a.size)));
          row.appendChild(info);
          row.appendChild(el("a", { class: "btn" + (os.id === mine ? " primary" : ""), href: a.browser_download_url }, "Download"));
          list.appendChild(row);
        });
        block.appendChild(list);
        target.appendChild(block);
      });
    })
    .catch(function (e) {
      showNoRelease("The page could not read the release list (" + e.message + ").");
    });
})();
