## Purpose

Defines the Wearhouse app shell inspired by Steam Big Picture: destinations, the Desktop and Focus presentations, spatial navigation for keyboard, pointer and touch, overlays, the hint bar, and the settings that change the whole app.

## ADDED Requirements

### Requirement: Destinations and utilities
The shell SHALL provide Home and the primary destinations Catalogue, Wardrobe, Community and Profile, together with:
- search;
- wishlist and cart counts;
- notifications with the unread count from `GET /me/notifications/unread-count`;
- the friends feed;
- a live clock in the user's time zone (Asia/Jakarta by default);
- an account menu containing Profile, Redeem a garment, Orders, Settings, About and Sign out.

A staff entry SHALL appear only when `/me` capabilities include a staff capability. At widths of 430 px and below, the primary destinations SHALL use a bottom navigation bar.

#### Scenario: Customer sees no staff entry
- **WHEN** a signed-in customer without staff capabilities opens the account menu
- **THEN** no staff or admin entry is present anywhere in the shell

### Requirement: Desktop and Focus presentations
The shell SHALL offer two presentations of the same routes and data:
- **Desktop:** navigation bars, sidebars, grids and dense metadata.
- **Focus mode:** large horizontal rails with one focused tile, a detail zone beneath the rail, quiet chrome and a footer hint bar.

The choice SHALL persist on the device. Focus mode SHALL always use the dark theme. Desktop SHALL follow the `theme` setting.

#### Scenario: Switching keeps place
- **WHEN** a user viewing a product in Desktop switches to Focus mode
- **THEN** the same product route is shown in Focus layout without refetching unchanged data

### Requirement: Selection drives the page
In Focus mode, moving focus to a tile SHALL:
- update the backdrop (accent colour and a blurred wash of the item's image);
- update the detail zone (name, ownership or price state, the primary action);
- update the hint bar's available actions.

These updates SHALL behave the same for mouse hover, keyboard and touch. Rapid movement SHALL NOT cause flicker in the detail zone. Gamepad input is out of scope (owner decision, 2026-11-26).

#### Scenario: Keyboard focus updates detail
- **WHEN** a user presses the right arrow key in a catalogue rail
- **THEN** the next tile becomes focused, and the backdrop and detail zone show that product within one frame budget after the motion completes

### Requirement: Spatial navigation and input mapping
The shell SHALL support arrow-key movement within rails and grids, and between neighbouring rails, remembering the last focused position of each rail. The keyboard mapping SHALL be:
- Enter: select;
- Escape: back;
- `[` `]`: switch tabs;
- `/`: search;
- `M`: Main menu;
- `Q`: Quick access.

Every action SHALL also be reachable with Tab order and pointer alone. All focus targets SHALL be real links or buttons.

#### Scenario: Rail memory
- **WHEN** a user moves to the fourth tile of rail A, moves down to rail B, then back up
- **THEN** focus returns to the fourth tile of rail A

### Requirement: Overlays and hint bar
The Main menu (left) SHALL list Home, Catalogue, Wardrobe, Community, Profile, Settings and Sign out. Quick access (right) SHALL show notifications, pending friend requests, today's weather for the user's location, and toggles for theme, reduce motion and sound. Both overlays SHALL trap focus and return it to the opener when closed. In Focus mode the hint bar SHALL list the actions available on the focused object, and it SHALL be hidden on touch-only devices.

#### Scenario: Overlay focus return
- **WHEN** a user opens Quick access with the `Q` key and closes it with Escape
- **THEN** focus returns to the element that was focused before opening

### Requirement: Settings applied app-wide
After sign-in the app SHALL apply `theme`, `reduce_motion`, `language`, `sound_effects`, `sound_volume`, `wardrobe_view`, `wardrobe_group_by_slot` and `style_suggestions` from `GET /me/settings`. A change SHALL take effect immediately without a reload. UI sounds SHALL be silent unless `sound_effects` is true.

#### Scenario: Language switch
- **WHEN** a user sets `language` to `id`
- **THEN** all interface text, dates and currency switch to Indonesian formats immediately

### Requirement: Home
Signed-in Home SHALL prioritise daily dressing. It SHALL show, in this order:
- continue styling (recent looks);
- today (weather plus an explicit control to get suggestions);
- recently added;
- not worn recently;
- products for you;
- friends' activity.

Signed-out visitors and users with an empty wardrobe SHALL instead lead with catalogue discovery, with redeem and add-garment calls to action for the empty wardrobe.

#### Scenario: Empty wardrobe home
- **WHEN** a signed-in user with no wardrobe items opens Home
- **THEN** the first rail is catalogue discovery, and Redeem a garment and Add a garment are offered
