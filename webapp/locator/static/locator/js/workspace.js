/*
 * Workspace page: thumbnail grid on the left, map with a location pin on
 * the right. Selecting a thumbnail moves the pin to where that picture or
 * video was taken (from its EXIF/metadata). Dragging the pin or clicking
 * the map picks a new spot; the button under the map then writes it into
 * the selected files. When the pin hasn't been moved, the same button
 * re-reads the location from the files instead.
 *
 * "Show all" (map corner, or the "N with location" count) switches to an
 * overview: one pin per located file, grouped into numbered clusters when
 * close together. Nothing can be edited there; clicking a thumbnail, the
 * popup's "Edit location" button, "Back to selection" or Esc leaves it.
 *
 * Double-clicking a thumbnail opens the original file in a new tab.
 */
(function () {
  "use strict";

  const obj_root = document.getElementById("workspace");
  const str_folder = obj_root.dataset.folder;
  const str_media_url = obj_root.dataset.mediaUrl;
  const str_location_url = obj_root.dataset.locationUrl;
  const str_thumbnail_url = obj_root.dataset.thumbnailUrl;
  const str_file_url = obj_root.dataset.fileUrl;
  const str_csrf_token = document.querySelector("[name=csrfmiddlewaretoken]").value;

  const obj_grid = document.getElementById("thumb-grid");
  const obj_summary = document.getElementById("thumb-summary");
  const obj_selection_label = document.getElementById("map-selection");
  const obj_coords_label = document.getElementById("map-coords");
  const obj_status = document.getElementById("map-status");
  const obj_button = document.getElementById("location-button");

  const int_located_zoom = 15;
  let arr_items = [];
  let obj_selected = new Set();   // indexes into arr_items
  let int_anchor = -1;            // last plain-clicked index, for shift-click ranges
  let bool_pin_moved = false;
  let bool_busy = false;
  let bool_overview = false;
  let obj_cluster_group = null;

  // ---- Map ---------------------------------------------------------------

  const obj_map = L.map("map", { worldCopyJump: true }).setView([20, 0], 2);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    referrerPolicy: "strict-origin-when-cross-origin",
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  }).addTo(obj_map);
  L.control.scale().addTo(obj_map);

  const obj_marker = L.marker([20, 0], { draggable: true, autoPan: true });

  obj_marker.on("drag", function () { showCoords(obj_marker.getLatLng()); });
  obj_marker.on("dragend", function () { markPinMoved(); });

  obj_map.on("click", function (obj_event) {
    if (bool_overview) return;
    if (obj_selected.size === 0) {
      setStatus("Select a picture or video first.", "");
      return;
    }
    placePin(obj_event.latlng);
    markPinMoved();
  });

  function placePin(obj_latlng) {
    obj_marker.setLatLng(obj_latlng);
    if (!obj_map.hasLayer(obj_marker)) obj_marker.addTo(obj_map);
    showCoords(obj_latlng);
  }

  function showCoords(obj_latlng) {
    const obj_wrapped = L.latLng(obj_latlng).wrap();
    obj_coords_label.textContent =
      obj_wrapped.lat.toFixed(6) + ", " + obj_wrapped.lng.toFixed(6);
  }

  function markPinMoved() {
    bool_pin_moved = true;
    setStatus("New spot chosen. Press “Set new location” to save it into the file(s).", "");
    updateButton();
  }

  // ---- All-locations overview -------------------------------------------

  const OverviewControl = L.Control.extend({
    options: { position: "topright" },
    onAdd: function () {
      const obj_button_el = L.DomUtil.create("button", "map-control-btn leaflet-bar");
      obj_button_el.type = "button";
      obj_button_el.textContent = "📍 Show all";
      obj_button_el.title = "Show the location of every picture and video";
      L.DomEvent.disableClickPropagation(obj_button_el);
      L.DomEvent.on(obj_button_el, "click", toggleOverview);
      return obj_button_el;
    },
  });
  const obj_overview_control = new OverviewControl().addTo(obj_map);

  function toggleOverview() {
    if (bool_overview) {
      exitOverview();
      applySelection();
    } else {
      enterOverview();
    }
  }

  function enterOverview() {
    const arr_located = [];
    arr_items.forEach(function (dict_item, int_index) {
      if (dict_item.location) arr_located.push(int_index);
    });
    if (arr_located.length === 0) {
      setStatus("None of the files in this folder has a location yet.", "error");
      return;
    }

    bool_overview = true;
    if (obj_map.hasLayer(obj_marker)) obj_map.removeLayer(obj_marker);

    obj_cluster_group = L.markerClusterGroup({ showCoverageOnHover: false, maxClusterRadius: 50 });
    arr_located.forEach(function (int_index) {
      const dict_location = arr_items[int_index].location;
      const obj_pin = L.marker([dict_location.lat, dict_location.lon], { title: arr_items[int_index].name });
      obj_pin.bindPopup(function () { return buildPopup(int_index); }, {
        minWidth: 180,
        // Keep the popup clear of the "Back to selection" button in the corner.
        autoPanPaddingTopLeft: L.point(20, 70),
        autoPanPaddingBottomRight: L.point(20, 20),
      });
      obj_pin.on("click", function () { highlightThumb(int_index); });
      obj_cluster_group.addLayer(obj_pin);
    });
    obj_map.addLayer(obj_cluster_group);
    obj_map.fitBounds(obj_cluster_group.getBounds(), { padding: [40, 40], maxZoom: int_located_zoom });

    const obj_control_el = obj_overview_control.getContainer();
    obj_control_el.textContent = "Back to selection";
    obj_control_el.classList.add("is-active");
    obj_selection_label.textContent = "All locations · " + arr_located.length + " pin" +
      (arr_located.length === 1 ? "" : "s");
    obj_coords_label.textContent = "";
    setStatus("Overview — click a pin to see the picture. Click a thumbnail to go back to editing.", "");
    updateButton();
  }

  function exitOverview() {
    if (!bool_overview) return;
    bool_overview = false;
    if (obj_cluster_group) {
      obj_map.removeLayer(obj_cluster_group);
      obj_cluster_group = null;
    }
    const obj_control_el = obj_overview_control.getContainer();
    obj_control_el.textContent = "📍 Show all";
    obj_control_el.classList.remove("is-active");
    clearHighlight();
  }

  function buildPopup(int_index) {
    const dict_item = arr_items[int_index];
    const obj_card = document.createElement("div");
    obj_card.className = "popup-card";

    const obj_img = document.createElement("img");
    obj_img.className = "popup-thumb";
    obj_img.alt = dict_item.name;
    obj_img.src = thumbnailUrl(dict_item.name);

    const obj_name = document.createElement("div");
    obj_name.className = "popup-name";
    obj_name.textContent = dict_item.name;
    obj_name.title = dict_item.name;

    const obj_edit = document.createElement("button");
    obj_edit.type = "button";
    obj_edit.className = "btn btn-primary btn-small";
    obj_edit.textContent = "Edit location";
    obj_edit.addEventListener("click", function () {
      exitOverview();
      selectOnly(int_index);
      scrollToThumb(int_index);
    });

    obj_card.append(obj_img, obj_name, obj_edit);
    return obj_card;
  }

  function highlightThumb(int_index) {
    clearHighlight();
    obj_grid.children[int_index].classList.add("is-highlighted");
    scrollToThumb(int_index);
  }

  function clearHighlight() {
    obj_grid.querySelectorAll(".thumb.is-highlighted").forEach(function (obj_card) {
      obj_card.classList.remove("is-highlighted");
    });
  }

  function scrollToThumb(int_index) {
    obj_grid.children[int_index].scrollIntoView({ block: "nearest", behavior: "smooth" });
  }

  document.addEventListener("keydown", function (obj_event) {
    if (obj_event.key === "Escape" && bool_overview) {
      exitOverview();
      applySelection();
    }
  });

  function thumbnailUrl(str_name) {
    return str_thumbnail_url + "?folder=" + encodeURIComponent(str_folder) +
      "&name=" + encodeURIComponent(str_name);
  }

  function fileUrl(str_name) {
    return str_file_url + "?folder=" + encodeURIComponent(str_folder) +
      "&name=" + encodeURIComponent(str_name);
  }

  // ---- Thumbnails --------------------------------------------------------

  function loadMedia() {
    obj_summary.textContent = "Loading…";
    return fetch(str_media_url + "?folder=" + encodeURIComponent(str_folder))
      .then(function (obj_response) {
        if (!obj_response.ok) throw new Error("Couldn't list the folder (" + obj_response.status + ").");
        return obj_response.json();
      })
      .then(function (dict_data) {
        arr_items = dict_data.items;
        renderGrid();
        updateSummary();
        if (arr_items.length > 0) selectOnly(0);
      })
      .catch(function (obj_error) {
        obj_summary.textContent = obj_error.message;
      });
  }

  function renderGrid() {
    obj_grid.replaceChildren();
    if (arr_items.length === 0) {
      const obj_empty = document.createElement("p");
      obj_empty.textContent = "No pictures or videos in this folder.";
      obj_grid.appendChild(obj_empty);
      return;
    }
    arr_items.forEach(function (dict_item, int_index) {
      const obj_card = document.createElement("div");
      obj_card.className = "thumb";
      obj_card.setAttribute("role", "option");
      obj_card.dataset.index = String(int_index);
      obj_card.title = dict_item.name;

      const obj_img = document.createElement("img");
      obj_img.className = "thumb-img";
      obj_img.loading = "lazy";
      obj_img.alt = dict_item.name;
      obj_img.src = thumbnailUrl(dict_item.name);

      const obj_name = document.createElement("div");
      obj_name.className = "thumb-name";
      obj_name.textContent = dict_item.name;

      const obj_badges = document.createElement("div");
      obj_badges.className = "thumb-badges";

      obj_card.append(obj_img, obj_name, obj_badges);
      obj_card.addEventListener("click", onThumbClick);
      obj_card.addEventListener("dblclick", onThumbDoubleClick);
      obj_grid.appendChild(obj_card);
      renderBadges(int_index);
    });
  }

  function renderBadges(int_index) {
    const dict_item = arr_items[int_index];
    const obj_badges = obj_grid.children[int_index].querySelector(".thumb-badges");
    obj_badges.replaceChildren();

    const obj_gps = document.createElement("span");
    obj_gps.className = "badge " + (dict_item.location ? "badge-gps" : "badge-nogps");
    obj_gps.textContent = dict_item.location ? "GPS" : "No GPS";
    obj_badges.appendChild(obj_gps);

    const obj_kind = document.createElement("span");
    if (!dict_item.writable) {
      obj_kind.className = "badge badge-readonly";
      obj_kind.textContent = "Read-only";
      obj_kind.title = "This app can't write a location into this file type";
    } else {
      obj_kind.className = "badge";
      obj_kind.textContent = dict_item.kind === "video" ? "Video" : "";
      if (!obj_kind.textContent) obj_kind.style.display = "none";
    }
    obj_badges.appendChild(obj_kind);
  }

  function updateSummary() {
    const int_located = arr_items.filter(function (dict_item) { return dict_item.location; }).length;
    const obj_count_button = document.createElement("button");
    obj_count_button.type = "button";
    obj_count_button.className = "link-button";
    obj_count_button.textContent = int_located + " with location";
    obj_count_button.title = "Show all of them on the map";
    obj_count_button.disabled = int_located === 0;
    obj_count_button.addEventListener("click", function () {
      if (!bool_overview) enterOverview();
    });
    obj_summary.replaceChildren(
      document.createTextNode(arr_items.length + " item" + (arr_items.length === 1 ? "" : "s") + " · "),
      obj_count_button
    );
  }

  function onThumbClick(obj_event) {
    const int_index = Number(obj_event.currentTarget.dataset.index);
    exitOverview();
    if (obj_event.shiftKey && int_anchor >= 0) {
      const int_from = Math.min(int_anchor, int_index);
      const int_to = Math.max(int_anchor, int_index);
      obj_selected = new Set();
      for (let int_i = int_from; int_i <= int_to; int_i++) obj_selected.add(int_i);
      applySelection();
    } else if (obj_event.ctrlKey || obj_event.metaKey) {
      if (obj_selected.has(int_index) && obj_selected.size > 1) obj_selected.delete(int_index);
      else obj_selected.add(int_index);
      int_anchor = int_index;
      applySelection();
    } else {
      selectOnly(int_index);
    }
  }

  function onThumbDoubleClick(obj_event) {
    const dict_item = arr_items[Number(obj_event.currentTarget.dataset.index)];
    window.open(fileUrl(dict_item.name), "_blank", "noopener");
  }

  function selectOnly(int_index) {
    obj_selected = new Set([int_index]);
    int_anchor = int_index;
    applySelection();
  }

  // ---- Selection -> pin --------------------------------------------------

  function selectedIndexes() {
    return Array.from(obj_selected).sort(function (int_a, int_b) { return int_a - int_b; });
  }

  function applySelection() {
    Array.from(obj_grid.children).forEach(function (obj_card, int_index) {
      const bool_on = obj_selected.has(int_index);
      obj_card.classList.toggle("is-selected", bool_on);
      obj_card.setAttribute("aria-selected", bool_on ? "true" : "false");
    });

    const arr_indexes = selectedIndexes();
    if (arr_indexes.length === 1) {
      obj_selection_label.textContent = arr_items[arr_indexes[0]].name;
    } else {
      obj_selection_label.textContent = arr_indexes.length + " items selected";
    }
    bool_pin_moved = false;
    showPinForSelection();
    updateButton();
  }

  function showPinForSelection() {
    const arr_indexes = selectedIndexes();
    const arr_located = arr_indexes.filter(function (int_i) { return arr_items[int_i].location; });
    const arr_readonly = arr_indexes.filter(function (int_i) { return !arr_items[int_i].writable; });

    if (arr_located.length > 0) {
      const dict_location = arr_items[arr_located[0]].location;
      const obj_latlng = L.latLng(dict_location.lat, dict_location.lon);
      placePin(obj_latlng);
      obj_map.flyTo(obj_latlng, Math.max(obj_map.getZoom(), int_located_zoom), { duration: 0.6 });
      let str_message = arr_indexes.length === 1
        ? "Location from the file. Drag the pin or click the map to change it."
        : arr_located.length + " of " + arr_indexes.length + " selected have a location; showing the first.";
      if (arr_readonly.length > 0) str_message += " " + readonlyNote(arr_readonly.length);
      setStatus(str_message, "");
    } else {
      placePin(obj_map.getCenter());
      obj_coords_label.textContent = "No location yet";
      let str_message = "No location saved in " + (arr_indexes.length === 1 ? "this file" : "these files") +
        ". Drag the pin or click the map to choose one.";
      if (arr_readonly.length > 0) str_message += " " + readonlyNote(arr_readonly.length);
      setStatus(str_message, "");
    }
  }

  function readonlyNote(int_count) {
    return int_count + " selected file" + (int_count === 1 ? " is" : "s are") + " read-only and won't be changed.";
  }

  function updateButton() {
    if (bool_overview) {
      obj_button.textContent = "Refresh location";
      obj_button.disabled = true;
      return;
    }
    const bool_any_writable = selectedIndexes().some(function (int_i) { return arr_items[int_i].writable; });
    if (bool_pin_moved) {
      obj_button.textContent = "Set new location";
      obj_button.disabled = bool_busy || !bool_any_writable;
    } else {
      obj_button.textContent = "Refresh location";
      obj_button.disabled = bool_busy || obj_selected.size === 0;
    }
  }

  function setStatus(str_message, str_kind) {
    obj_status.textContent = str_message;
    obj_status.classList.toggle("is-error", str_kind === "error");
    obj_status.classList.toggle("is-ok", str_kind === "ok");
  }

  // ---- Button: refresh / set new location --------------------------------

  obj_button.addEventListener("click", function () {
    if (bool_busy || obj_selected.size === 0) return;
    bool_busy = true;
    updateButton();
    const obj_promise = bool_pin_moved ? saveLocation() : refreshLocation();
    obj_promise.finally(function () {
      bool_busy = false;
      updateButton();
    });
  });

  function refreshLocation() {
    const arr_indexes = selectedIndexes();
    setStatus("Reading location…", "");
    return Promise.all(arr_indexes.map(function (int_i) {
      const str_url = str_location_url + "?folder=" + encodeURIComponent(str_folder) +
        "&name=" + encodeURIComponent(arr_items[int_i].name);
      return fetch(str_url)
        .then(function (obj_response) { return obj_response.json(); })
        .then(function (dict_data) {
          if (!dict_data.error) {
            arr_items[int_i].location = dict_data.location;
            renderBadges(int_i);
          }
        });
    }))
      .then(function () {
        updateSummary();
        bool_pin_moved = false;
        showPinForSelection();
      })
      .catch(function (obj_error) { setStatus("Couldn't read the location: " + obj_error.message, "error"); });
  }

  function saveLocation() {
    const arr_indexes = selectedIndexes().filter(function (int_i) { return arr_items[int_i].writable; });
    const obj_latlng = obj_marker.getLatLng().wrap();
    setStatus("Writing location into " + arr_indexes.length + " file(s)…", "");

    return fetch(str_location_url, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": str_csrf_token },
      body: JSON.stringify({
        folder: str_folder,
        names: arr_indexes.map(function (int_i) { return arr_items[int_i].name; }),
        lat: obj_latlng.lat,
        lon: obj_latlng.lng,
      }),
    })
      .then(function (obj_response) {
        if (!obj_response.ok) {
          return obj_response.text().then(function (str_text) { throw new Error(str_text); });
        }
        return obj_response.json();
      })
      .then(function (dict_data) {
        const dict_by_name = {};
        dict_data.results.forEach(function (dict_result) { dict_by_name[dict_result.name] = dict_result; });

        const arr_failed = [];
        arr_indexes.forEach(function (int_i) {
          const dict_result = dict_by_name[arr_items[int_i].name];
          if (dict_result && dict_result.ok) {
            arr_items[int_i].location = dict_result.location;
            renderBadges(int_i);
          } else if (dict_result) {
            arr_failed.push(dict_result.name + ": " + dict_result.error);
          }
        });
        updateSummary();
        bool_pin_moved = false;

        const int_saved = arr_indexes.length - arr_failed.length;
        if (arr_failed.length === 0) {
          setStatus("Saved the new location into " + int_saved + " file(s).", "ok");
        } else {
          setStatus("Saved " + int_saved + ", failed " + arr_failed.length + " — " + arr_failed.join("; "), "error");
        }
      })
      .catch(function (obj_error) { setStatus("Couldn't save: " + obj_error.message, "error"); });
  }

  loadMedia();
})();
