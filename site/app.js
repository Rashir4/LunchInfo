/* Avenylunch frontend. No dependencies.
   All scraped text is inserted via textContent — never innerHTML — since
   menu data comes from third-party sites. */
(() => {
  "use strict";

  const DAYS = [
    { key: "mon", label: "Mån", full: "Måndag" },
    { key: "tue", label: "Tis", full: "Tisdag" },
    { key: "wed", label: "Ons", full: "Onsdag" },
    { key: "thu", label: "Tors", full: "Torsdag" },
    { key: "fri", label: "Fre", full: "Fredag" },
  ];

  // Food-type ids as stored in data.json -> the label shown in the dropdown.
  const FOOD_TYPES = [
    ["veg", "Vegetariskt"],
    ["fisk", "Fisk & skaldjur"],
    ["kott", "Kött"],
    ["kyckling", "Kyckling"],
    ["gryta", "Gryta & curry"],
    ["pasta", "Pasta & pizza"],
    ["soppa", "Soppa"],
    ["sallad", "Sallad & bowls"],
    ["sushi", "Sushi"],
    ["nudlar", "Nudlar & wok"],
    ["burgare", "Burgare"],
  ];

  const el = {
    tabs: document.getElementById("day-tabs"),
    filter: document.getElementById("filter"),
    restaurant: document.getElementById("restaurant-filter"),
    cuisine: document.getElementById("cuisine-filter"),
    type: document.getElementById("type-filter"),
    clear: document.getElementById("clear-filters"),
    count: document.getElementById("result-count"),
    cards: document.getElementById("cards"),
    status: document.getElementById("status"),
    weekInfo: document.getElementById("week-info"),
  };

  let data = null;
  let selectedDay = todayKey();
  let query = "";
  let restaurantId = "";   // "" = all
  let cuisine = "";        // "" = all
  let foodType = "";       // "" = all

  function todayKey() {
    // getDay(): 0=Sunday … 6=Saturday. Weekends show Monday's menu.
    const idx = new Date().getDay();
    return idx >= 1 && idx <= 5 ? DAYS[idx - 1].key : "mon";
  }

  function showStatus(text, isError) {
    el.status.textContent = text;
    el.status.hidden = !text;
    el.status.classList.toggle("error", Boolean(isError));
  }

  function renderTabs() {
    el.tabs.textContent = "";
    for (const day of DAYS) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.setAttribute("role", "tab");
      btn.setAttribute("aria-selected", String(day.key === selectedDay));
      btn.textContent = day.label;
      btn.title = day.full;
      btn.addEventListener("click", () => {
        selectedDay = day.key;
        renderTabs();
        renderCards();
      });
      el.tabs.appendChild(btn);
    }
  }

  // Dishes shown for a restaurant on the selected day. When a food-type filter
  // is active the card lists only the matching dishes, so the answer to "show
  // me vegetarian" is the vegetarian dishes, not every dish at a place that
  // happens to have one.
  function visibleDishes(restaurant) {
    const dishes = restaurant.days?.[selectedDay] || [];
    if (!foodType) return dishes;
    return dishes.filter((d) => (d.types || []).includes(foodType));
  }

  function matches(restaurant) {
    if (restaurantId && restaurant.id !== restaurantId) return false;
    if (cuisine && restaurant.cuisine !== cuisine) return false;
    // A food-type filter hides restaurants with nothing of that type today,
    // but never hides one whose scrape failed — its menu is simply unknown.
    if (foodType && !restaurant.error && !visibleDishes(restaurant).length) return false;
    if (!query) return true;
    if (findMatches(restaurant.name, query).length) return true;
    return visibleDishes(restaurant).some((d) => findMatches(d.text, query).length);
  }

  // Append `text` to `parent`, wrapping case-insensitive matches of the
  // current query in <mark>. Built with text nodes only.
  //
  // Offsets come from a locale-aware search on the ORIGINAL string rather than
  // from indexOf on a lowercased copy: case folding can change length (\u0130
  // lowercases to two code units), which would shift every later slice.
  function appendHighlighted(parent, text) {
    if (!query) {
      parent.appendChild(document.createTextNode(text));
      return;
    }
    let pos = 0;
    for (const hit of findMatches(text, query)) {
      parent.appendChild(document.createTextNode(text.slice(pos, hit.start)));
      const mark = document.createElement("mark");
      mark.textContent = text.slice(hit.start, hit.end);
      parent.appendChild(mark);
      pos = hit.end;
    }
    parent.appendChild(document.createTextNode(text.slice(pos)));
  }

  // Case- and accent-insensitive substring search returning {start, end}
  // offsets into the ORIGINAL string.
  //
  // Folding changes length (å -> a, İ -> i̇, ß -> ss), so offsets cannot be
  // taken from a folded copy directly. Instead each folded character remembers
  // the original slice it came from, and matches are mapped back through it.
  // Accents are stripped rather than collated: Intl.Collator("sv") treats
  // å/ä/ö as distinct base letters, so "rakor" would not find "Räkor" — which
  // is exactly what someone on a non-Swedish keyboard types.
  function fold(text) {
    let folded = "";
    const starts = [];   // starts[i] = offset in `text` of folded char i
    const ends = [];     // ends[i]   = offset just past that original char
    let cursor = 0;
    for (const char of text) {          // iterates by code point
      const piece = char
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")   // drop combining marks
        .toLowerCase();
      for (let i = 0; i < piece.length; i += 1) {
        starts.push(cursor);
        ends.push(cursor + char.length);
      }
      folded += piece;
      cursor += char.length;            // code units, matching String.slice
    }
    return { folded, starts, ends, length: cursor };
  }

  function findMatches(text, needle) {
    const hits = [];
    const hay = fold(text);
    const pin = fold(needle).folded;
    if (!pin) return hits;
    let from = 0;
    for (;;) {
      const at = hay.folded.indexOf(pin, from);
      if (at === -1) break;
      let end = hay.ends[at + pin.length - 1];
      // Absorb characters that folded away (combining marks) so a highlight
      // never ends in the middle of a grapheme.
      while (end < hay.length && hay.starts.indexOf(end) === -1) end += 1;
      hits.push({ start: hay.starts[at], end });
      from = at + pin.length;
    }
    return hits;
  }

  // Google Maps search link. The name is included alongside the address so the
  // pin lands on the restaurant rather than just the building — several of
  // these share an address (hotels, Gothia Towers, the Chalmers campus).
  function mapsUrl(r) {
    const parts = [r.name, r.address].filter(Boolean);
    let query = parts.join(", ");
    if (!/göteborg|gothenburg/i.test(query)) query += ", Göteborg";
    return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(query)}`;
  }

  function buildCard(r) {
    const card = document.createElement("article");
    card.className = "card" + (r.error ? " failed" : "");

    const head = document.createElement("div");
    head.className = "card-head";
    const h2 = document.createElement("h2");
    const link = document.createElement("a");
    link.href = r.url || r.menu_url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    appendHighlighted(link, r.name);
    h2.appendChild(link);
    head.appendChild(h2);
    if (Number.isFinite(r.walk_minutes)) {
      const walk = document.createElement("span");
      walk.className = "walk";
      walk.textContent = `🚶 ${r.walk_minutes} min`;
      head.appendChild(walk);
    }
    card.appendChild(head);

    const facts = document.createElement("p");
    facts.className = "facts";
    for (const fact of [r.price, r.lunch_hours]) {
      if (!fact) continue;
      const span = document.createElement("span");
      span.textContent = fact;
      facts.appendChild(span);
    }
    if (r.address) {
      const map = document.createElement("a");
      map.className = "address";
      map.href = mapsUrl(r);
      map.target = "_blank";
      map.rel = "noopener noreferrer";
      map.title = `Visa ${r.name} på Google Maps`;
      map.textContent = `📍 ${r.address}`;
      facts.appendChild(map);
    }
    if (facts.childNodes.length) card.appendChild(facts);

    if (r.static_menu) {
      const note = document.createElement("p");
      note.className = "fixed-menu";
      note.textContent = "Fast veckoschema — samma rätter varje vecka";
      card.appendChild(note);
    }

    if (Number.isFinite(r.stale_week)) {
      const warn = document.createElement("p");
      warn.className = "stale";
      warn.textContent = `⚠ Restaurangen har inte publicerat v.${data.week} än — visar v.${r.stale_week}`;
      card.appendChild(warn);
    }

    const dishes = visibleDishes(r);
    if (r.error) {
      const p = document.createElement("p");
      p.className = "no-menu";
      p.textContent = "Kunde inte hämta menyn just nu.";
      card.appendChild(p);
    } else if (!dishes.length) {
      const p = document.createElement("p");
      p.className = "no-menu";
      p.textContent = "Ingen meny publicerad för denna dag.";
      card.appendChild(p);
    } else {
      const ul = document.createElement("ul");
      ul.className = "dishes";
      for (const dish of dishes) {
        const li = document.createElement("li");
        if (dish.tag === "veg" || dish.tag === "fisk") {
          const tag = document.createElement("span");
          tag.className = `tag ${dish.tag}`;
          tag.textContent = dish.tag;
          li.appendChild(tag);
        }
        appendHighlighted(li, dish.text);
        ul.appendChild(li);
      }
      card.appendChild(ul);
    }

    const menuLink = document.createElement("p");
    menuLink.className = "menu-link";
    const a = document.createElement("a");
    a.href = r.menu_url || r.url;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    a.textContent = "Se hela menyn →";
    menuLink.appendChild(a);
    card.appendChild(menuLink);

    return card;
  }

  function addOption(select, value, label) {
    const opt = document.createElement("option");
    opt.value = value;
    opt.textContent = label;
    select.appendChild(opt);
  }

  function buildFilters() {
    const restaurants = [...data.restaurants].sort((a, b) =>
      a.name.localeCompare(b.name, "sv")
    );
    el.restaurant.textContent = "";
    addOption(el.restaurant, "", `Alla restauranger (${restaurants.length})`);
    for (const r of restaurants) addOption(el.restaurant, r.id, r.name);

    const cuisines = [...new Set(data.restaurants.map((r) => r.cuisine).filter(Boolean))]
      .sort((a, b) => a.localeCompare(b, "sv"));
    el.cuisine.textContent = "";
    addOption(el.cuisine, "", "Alla kök");
    for (const c of cuisines) {
      const n = data.restaurants.filter((r) => r.cuisine === c).length;
      addOption(el.cuisine, c, `${c} (${n})`);
    }

    el.type.textContent = "";
    addOption(el.type, "", "All mat");
    // Offer only types that actually occur this week, so the list never
    // promises a category that returns nothing on every day.
    const present = new Set(
      data.restaurants.flatMap((r) =>
        Object.values(r.days || {}).flatMap((ds) => ds.flatMap((d) => d.types || []))
      )
    );
    for (const [id, label] of FOOD_TYPES) {
      if (present.has(id)) addOption(el.type, id, label);
    }
  }

  function renderCount(shown, total) {
    const filtered = Boolean(query || restaurantId || cuisine || foodType);
    el.clear.hidden = !filtered;
    el.count.textContent = filtered
      ? `Visar ${shown} av ${total} restauranger`
      : "";
  }

  function renderCards() {
    el.cards.textContent = "";
    if (!data) return;
    const visible = data.restaurants.filter(matches);
    renderCount(visible.length, data.restaurants.length);
    if (!visible.length) {
      showStatus("Inga restauranger matchar filtret. Prova att rensa det.", false);
      return;
    }
    showStatus("", false);
    for (const r of visible) el.cards.appendChild(buildCard(r));
  }

  function renderWeekInfo() {
    if (!data) return;
    let text = `Vecka ${data.week}, ${data.year}`;
    if (data.generated_at) {
      const when = new Date(data.generated_at);
      if (!Number.isNaN(when.getTime())) {
        text += ` · uppdaterad ${when.toLocaleString("sv-SE", {
          weekday: "long", day: "numeric", month: "long",
          hour: "2-digit", minute: "2-digit",
        })}`;
      }
    }
    el.weekInfo.textContent = text;
    el.weekInfo.hidden = false;
  }

  el.filter.addEventListener("input", () => {
    query = el.filter.value.trim();
    renderCards();
  });

  el.restaurant.addEventListener("change", () => {
    restaurantId = el.restaurant.value;
    renderCards();
  });

  el.cuisine.addEventListener("change", () => {
    cuisine = el.cuisine.value;
    renderCards();
  });

  el.type.addEventListener("change", () => {
    foodType = el.type.value;
    renderCards();
  });

  el.clear.addEventListener("click", () => {
    query = restaurantId = cuisine = foodType = "";
    el.filter.value = "";
    el.restaurant.value = el.cuisine.value = el.type.value = "";
    renderCards();
    el.filter.focus();
  });

  renderTabs();
  showStatus("Hämtar veckans menyer…", false);

  fetch("data.json", { cache: "no-store" })
    .then((resp) => {
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      return resp.json();
    })
    .then((json) => {
      if (!json || !Array.isArray(json.restaurants)) {
        throw new Error("oväntat dataformat");
      }
      data = json;
      renderWeekInfo();
      buildFilters();
      renderCards();
    })
    .catch((err) => {
      showStatus(
        `Kunde inte läsa menydata (${err.message}). Kör skrapan och ladda om sidan.`,
        true
      );
    });
})();
