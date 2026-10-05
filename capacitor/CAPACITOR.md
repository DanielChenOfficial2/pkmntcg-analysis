# Capacitor setup

Capacitor packages the existing static site in `website/`; it does not introduce a framework or a second copy of the web assets. `webDir` in `capacitor.config.json` points directly to that directory, which contains the root `index.html`. Native platform projects live in `capacitor/android/` and `capacitor/ios/`. The pages, card images, and relative navigation links are copied unchanged into the native app.

Tailwind is compiled locally from the classes in the HTML pages. The generated `website/tailwind.css` is checked in so the browser site works without a build step or a Tailwind CDN connection. `npm run build` converts any remaining Tailwind CDN references throughout `website/`, then regenerates the stylesheet from the classes in every page. Run it after generating or changing pages:

```sh
npm install
npm run build
```

### Preparing generated HTML

When a generator creates new HTML pages that still include the Tailwind CDN script, the regular build converts them automatically. To convert only the new files (or the directory containing them) without touching other pages:

```sh
npm run prepare:capacitor -- website/new-page.html website/generated-pages
```

The converter updates only HTML files that still load `https://cdn.tailwindcss.com`; it leaves other files and already-prepared pages unchanged. With no paths supplied, it scans all of `website/`:

```sh
npm run prepare:capacitor
npm run build
```

After using the targeted converter, run `npm run build` to refresh the stylesheet with classes from the new pages.

## Android

Install Node.js 22 or newer, Android Studio, Android SDK Platform 36, and JDK 21. The generated Android project uses Gradle 8.14.3; Android Studio's bundled JDK 25 is too new for this Gradle version. In Android Studio, set **Settings > Build, Execution, Deployment > Build Tools > Gradle > Gradle JDK** to a JDK 21 installation. Then, from the repository root:

```sh
npm install
npm run cap:add:android
npm run cap:open:android
```

The first command builds the local stylesheet and creates the native `capacitor/android/` project. To copy subsequent web changes into the native project, run `npm run cap:sync:android`.

## iOS

iOS project generation and builds require macOS, Node.js 22 or newer, Xcode 26 or newer, and the Xcode Command Line Tools. From the repository root on macOS:

```sh
npm install
npm run cap:add:ios
npm run cap:open:ios
```

The first command builds the local stylesheet and creates the native `capacitor/ios/` project. To copy subsequent web changes into the native project, run `npm run cap:sync:ios`.

`npm run cap:sync` rebuilds the stylesheet and syncs every platform already added to the project. Generated native project files should be committed when they are created so platform-specific configuration is preserved.

Platform generation does not submit an app to a store or guarantee approval. Distribution still requires platform signing, store metadata, privacy disclosures, and compliance with each store's review requirements.
