export class SessionStorageService {
  private static readonly KEY = "dbablo-miniapp-token";

  public static getToken(): string | null {
    return window.localStorage.getItem(this.KEY);
  }

  public static setToken(token: string): void {
    window.localStorage.setItem(this.KEY, token);
  }
}
