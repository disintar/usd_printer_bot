export interface TelegramUser {
  id: number;
  username?: string;
  first_name?: string;
  last_name?: string;
}

interface TelegramWebApp {
  ready: () => void;
  expand: () => void;
  isVerticalSwipesEnabled?: boolean;
  disableVerticalSwipes?: () => void;
  setHeaderColor?: (color: string) => void;
  setBackgroundColor?: (color: string) => void;
  HapticFeedback?: {
    impactOccurred?: (style: "light" | "medium" | "heavy" | "rigid" | "soft") => void;
    notificationOccurred?: (type: "error" | "success" | "warning") => void;
    selectionChanged?: () => void;
  };
  initDataUnsafe?: {
    user?: TelegramUser;
  };
}

interface TelegramWindow extends Window {
  Telegram?: {
    WebApp?: TelegramWebApp;
  };
}

export class TelegramWebAppService {
  private static lastSelectionHapticAt = 0;

  public static initialize(): void {
    const app = this.getWebApp();
    if (app === null) {
      return;
    }
    app.ready();
    app.expand();
    app.disableVerticalSwipes?.();
    app.setHeaderColor?.("#0f141b");
    app.setBackgroundColor?.("#0f141b");
  }

  public static getUser(): TelegramUser | null {
    const app = this.getWebApp();
    if (app?.initDataUnsafe?.user !== undefined) {
      return app.initDataUnsafe.user;
    }
    return this.getDevelopmentUser();
  }

  public static hapticSelectionChanged(): void {
    const now = Date.now();
    if (now - this.lastSelectionHapticAt < 35) {
      return;
    }
    this.lastSelectionHapticAt = now;

    const app = this.getWebApp();
    app?.HapticFeedback?.selectionChanged?.();
  }

  public static shouldApplyIosTopInset(): boolean {
    return this.isTelegramWebApp() && this.isIosDevice();
  }

  public static isTelegramWebApp(): boolean {
    return this.getWebApp() !== null;
  }

  private static isIosDevice(): boolean {
    const ua = window.navigator.userAgent;
    const hasTouch = window.navigator.maxTouchPoints > 1;
    const isIphoneIpadIpod = /iPhone|iPad|iPod/i.test(ua);
    const isIpadDesktopMode =
      window.navigator.platform === "MacIntel" && hasTouch;
    return isIphoneIpadIpod || isIpadDesktopMode;
  }

  private static getWebApp(): TelegramWebApp | null {
    const telegramWindow = window as TelegramWindow;
    return telegramWindow.Telegram?.WebApp ?? null;
  }

  private static getDevelopmentUser(): TelegramUser | null {
    const userId = import.meta.env.VITE_DEV_TELEGRAM_USER_ID;
    if (userId === undefined || userId.trim() === "") {
      return null;
    }

    return {
      id: Number(userId),
      username: import.meta.env.VITE_DEV_TELEGRAM_USERNAME
    };
  }
}
