import os
import sys
from dataclasses import dataclass

import pygame as pg


os.chdir(os.path.dirname(os.path.abspath(__file__)))


# ===== 定数 =====
WIDTH = 1000  # 画面の幅
HEIGHT = 600  # 画面の高さ
FPS = 60  # 1秒あたりのフレーム数
GROUND_Y = 520  # 地面のy座標（キャラの足元）
GRAVITY = 1  # 1フレームごとに加算される落下速度
ROUND_TIME = 60  # 1ラウンドの制限時間（秒）

FIGHTER_W = 80  # キャラの幅（当たり判定）
FIGHTER_H = 160  # キャラの高さ（当たり判定）
MAX_HP = 100  # 最大体力
WALK_SPEED = 5  # 歩く速さ
JUMP_POWER = 20  # ジャンプの初速

ATTACK_W = 70  # 攻撃判定の幅
ATTACK_H = 40  # 攻撃判定の高さ
ATTACK_DAMAGE = 8  # 攻撃1回のダメージ
ATTACK_FRAMES = 15  # 攻撃が出ている時間（フレーム）
ATTACK_COOLDOWN = 25  # 次に攻撃できるまでの時間（フレーム）
HITSTUN_FRAMES = 12  # 攻撃を受けて動けない時間（フレーム）
KNOCKBACK = 12  # 攻撃を受けたときに押し戻される距離

# =====防御関連の定数=====
BARRIER_W = 80  # 防御判定の幅
BARRIER_H = 40  # 防御判定の高さ
BARRIER_FRAMES = 15  # 防御が出ている時間（フレーム）
BARRIER_COOLDOWN = 5  # 次に防御できるまでの時間（フレーム）
BARRIER_KNOCKBACK = 6  # バリア状態で攻撃を受けたときに押し戻される距離
BARRIER_DAMAGE_ULTIMATE_ATTACK = 2  # 必殺技を防御したときのダメージ


@dataclass
class KeyConfig:
    """
    プレイヤーごとのキー割り当て
    """
    left: int
    right: int
    jump: int
    attack: int
    barrier_up: int  # 上防御
    barrier_md: int  # 中防御


P1_KEYS = KeyConfig(
    left=pg.K_a,
    right=pg.K_d,
    jump=pg.K_w,
    attack=pg.K_f,
    barrier_up=pg.K_r,
    barrier_md=pg.K_t
    )
P2_KEYS = KeyConfig(
    left=pg.K_LEFT,
    right=pg.K_RIGHT,
    jump=pg.K_UP,
    attack=pg.K_l,
    barrier_up=pg.K_o,
    barrier_md=pg.K_p
    )


def load_fighter_image(path: str, color: tuple[int, int, int]) -> pg.Surface:
    """
    キャラ画像を読み込む。画像がなければ単色の四角で代用する
    引数 path：画像ファイルのパス
    引数 color：画像がないときの代わりの色
    戻り値：右向きのキャラ画像Surface
    """
    if os.path.exists(path):
        img = pg.image.load(path).convert_alpha()
        return pg.transform.scale(img, (FIGHTER_W, FIGHTER_H))
    img = pg.Surface((FIGHTER_W, FIGHTER_H))
    img.fill(color)
    pg.draw.rect(img, (255, 255, 255), (FIGHTER_W - 25, 20, 12, 12))  # 向きが分かるように目を描く
    return img


class Fighter(pg.sprite.Sprite):
    """
    格闘キャラクターに関するクラス
    """

    def __init__(self, name: str, x: int, facing: int, keys: KeyConfig,
                 img_path: str, color: tuple[int, int, int]) -> None:
        """
        キャラクターを生成する
        引数 name：表示名
        引数 x：初期位置のx座標（中心）
        引数 facing：向き（右:+1, 左:-1）
        引数 keys：操作キーの設定
        引数 img_path：右向き画像のパス
        引数 color：画像がないときの代わりの色
        """
        super().__init__()
        self.name = name
        self.keys = keys
        self.facing = facing
        self.img_right = load_fighter_image(img_path, color)
        self.img_left = pg.transform.flip(self.img_right, True, False)
        self.image = self.img_right if facing == 1 else self.img_left
        self.rect = self.image.get_rect()
        self.rect.centerx = x
        self.rect.bottom = GROUND_Y
        self.vy = 0  # 縦方向の速度
        self.hp = MAX_HP

        self.attack_timer = 0  # 攻撃判定が残っているフレーム数
        self.cooldown = 0  # 次の攻撃までの待ちフレーム数

        self.barrier_timer = 0  # 防御判定が残っているフレーム数
        self.barrier_cooldown = 0  # 次の防御までの待ちフレーム数
        self.barrier_type = ""  # "up"または"md"

        self.hitstun = 0  # のけぞりの残りフレーム数
        self.has_hit = False  # 今回の攻撃がすでに当たったか

    def is_on_ground(self) -> bool:
        """
        地面に立っているかを返す
        """
        return self.rect.bottom >= GROUND_Y

    def handle_input(self, key_lst: pg.key.ScancodeWrapper) -> None:
        """
        押されているキーに応じて移動・ジャンプ・攻撃・防御を行う
        引数 key_lst：押下キーの真理値リスト
        """
        if self.hitstun > 0:  # のけぞり中は操作できない
            return
        dx = 0
        if key_lst[self.keys.left]:
            dx -= WALK_SPEED
        if key_lst[self.keys.right]:
            dx += WALK_SPEED
        self.rect.x += dx
        if key_lst[self.keys.jump] and self.is_on_ground():
            self.vy = -JUMP_POWER

        # 防御中は攻撃を出せないように self.barrier_timer == 0を追加
        if key_lst[self.keys.attack] and self.cooldown == 0 and self.barrier_timer == 0:
            self.attack_timer = ATTACK_FRAMES
            self.cooldown = ATTACK_COOLDOWN
            self.has_hit = False

        # 攻撃中は防御を出せないように self.attack_timer == 0を条件に設定
        if key_lst[self.keys.barrier_up] and self.barrier_cooldown == 0 and self.attack_timer == 0:
            self.barrier_timer = BARRIER_FRAMES
            self.barrier_cooldown = BARRIER_COOLDOWN
            self.barrier_type = "up"
        elif key_lst[self.keys.barrier_md] and self.barrier_cooldown == 0 and self.attack_timer == 0:
            self.barrier_timer = BARRIER_FRAMES
            self.barrier_cooldown = BARRIER_COOLDOWN
            self.barrier_type = "md"

    def face_to(self, other: "Fighter") -> None:
        """
        相手のいる方向を向く
        引数 other：相手キャラ
        """
        self.facing = 1 if other.rect.centerx >= self.rect.centerx else -1
        self.image = self.img_right if self.facing == 1 else self.img_left

    def get_attack_rect(self) -> pg.Rect | None:
        """
        攻撃判定の矩形を返す（攻撃中でなければNone）
        """
        if self.attack_timer <= 0:
            return None
        atk = pg.Rect(0, 0, ATTACK_W, ATTACK_H)
        atk.centery = self.rect.top + FIGHTER_H // 3
        if self.facing == 1:
            atk.left = self.rect.right
        else:
            atk.right = self.rect.left
        return atk

    # 防御判定の矩形を取得するメソッド
    def get_barrier_rect(self) -> pg.Rect | None:
        """
        防御判定の矩形を返す（防御中でなければNone）
        """
        if self.barrier_timer <= 0:
            return None
        bar = pg.Rect(0, 0, BARRIER_W, BARRIER_H)

        # 上段は少し高め、中段は中央に判定を配置する
        if self.barrier_type == "up":
            bar.centery = self.rect.top + FIGHTER_H // 4
        else:
            bar.centery = self.rect.centery

        if self.facing == 1:
            bar.left = self.rect.right - FIGHTER_W
        else:
            bar.right = self.rect.left + FIGHTER_W
        return bar

    # ガード成功時の処理メソッド
    def block_attack(self, from_dir: int) -> None:
        """
        防御成功時にノックバックする処理
        引数 from_dir：押し戻される向き（右:+1, 左:-1）
        """
        self.rect.x += BARRIER_KNOCKBACK * from_dir
        self.rect.clamp_ip(pg.Rect(0, 0, WIDTH, HEIGHT))

    def take_damage(self, damage: int, from_dir: int) -> None:
        """
        ダメージを受けてのけぞる
        引数 damage：受けるダメージ量
        引数 from_dir：押し戻される向き（右:+1, 左:-1）
        """
        self.hp = max(0, self.hp - damage)
        self.hitstun = HITSTUN_FRAMES
        self.attack_timer = 0 #  攻撃を潰される
        self.barrier_timer = 0 #  ダメージを受けたら防御も潰される
        self.rect.x += KNOCKBACK * from_dir
        self.rect.clamp_ip(pg.Rect(0, 0, WIDTH, HEIGHT))  # 画面外に押し出されないようにする

    def update(self) -> None:
        """
        重力・タイマー・画面端の処理を行う
        """
        self.vy += GRAVITY
        self.rect.y += self.vy
        if self.rect.bottom >= GROUND_Y:
            self.rect.bottom = GROUND_Y
            self.vy = 0
        self.rect.clamp_ip(pg.Rect(0, 0, WIDTH, HEIGHT))
        self.attack_timer = max(0, self.attack_timer - 1)
        self.cooldown = max(0, self.cooldown - 1)

        # バリアのタイマーを追加
        self.barrier_timer = max(0, self.barrier_timer - 1)
        self.barrier_cooldown = max(0, self.barrier_cooldown - 1)

        self.hitstun = max(0, self.hitstun - 1)

    def draw(self, screen: pg.Surface) -> None:
        """
        キャラと攻撃・防御判定を描画する
        引数 screen：画面Surface
        """
        screen.blit(self.image, self.rect)
        atk = self.get_attack_rect()
        if atk is not None:
            pg.draw.rect(screen, (255, 220, 0), atk, 3)  # 攻撃判定は黄色

        # 防御判定の描画
        bar = self.get_barrier_rect()
        if bar is not None:
            color = (0, 200, 255) if self.barrier_type == "up" else (0, 255, 100)
            pg.draw.rect(screen, color, bar, 3)  # 防御判定（上段:水色、中段:緑色)


def check_hit(attacker: Fighter, defender: Fighter) -> None:
    """
    攻撃側の攻撃が防御側に当たったか判定し、処理を行う
    引数 attacker：攻撃側キャラ
    引数 defender：防御側キャラ
    """

    atk = attacker.get_attack_rect()
    if atk is None or attacker.has_hit:
        return

    # 防御判定への衝突チェック
    # 本体へのダメージ処理より先に判定
    bar = defender.get_barrier_rect()
    if bar is not None and atk.colliderect(bar):
        defender.block_attack(attacker.facing)
        attacker.has_hit = True
        return

    # 本体への衝突チェック
    if atk.colliderect(defender.rect):
        defender.take_damage(ATTACK_DAMAGE, attacker.facing)
        attacker.has_hit = True


def push_apart(f1: Fighter, f2: Fighter) -> None:
    """
    キャラ同士が重ならないように押し離す
    引数 f1, f2：キャラ
    """
    if not f1.rect.colliderect(f2.rect):
        return
    overlap = min(f1.rect.right, f2.rect.right) - max(f1.rect.left, f2.rect.left)
    shift = overlap // 2 + 1
    if f1.rect.centerx <= f2.rect.centerx:
        f1.rect.x -= shift
        f2.rect.x += shift
    else:
        f1.rect.x += shift
        f2.rect.x -= shift
    f1.rect.clamp_ip(pg.Rect(0, 0, WIDTH, HEIGHT))
    f2.rect.clamp_ip(pg.Rect(0, 0, WIDTH, HEIGHT))


def draw_hp_bar(screen: pg.Surface, fighter: Fighter, x: int, font: pg.font.Font) -> None:
    """
    体力ゲージと名前を描画する
    引数 screen：画面Surface
    引数 fighter：対象キャラ
    引数 x：ゲージ左端のx座標
    引数 font：名前表示用フォント
    """
    bar_w, bar_h = 400, 24
    pg.draw.rect(screen, (80, 0, 0), (x, 20, bar_w, bar_h))
    hp_w = bar_w * fighter.hp // MAX_HP
    pg.draw.rect(screen, (0, 200, 60), (x, 20, hp_w, bar_h))
    pg.draw.rect(screen, (255, 255, 255), (x, 20, bar_w, bar_h), 2)
    screen.blit(font.render(fighter.name, True, (255, 255, 255)), (x, 50))


def draw_center_text(screen: pg.Surface, text: str, font: pg.font.Font, y: int) -> None:
    """
    画面中央に文字を描画する
    引数 screen：画面Surface
    引数 text：表示する文字列
    引数 font：フォント
    引数 y：文字の中心のy座標
    """
    txt = font.render(text, True, (255, 255, 255))
    screen.blit(txt, txt.get_rect(center=(WIDTH // 2, y)))


def judge_winner(p1: Fighter, p2: Fighter) -> str:
    """
    勝者を判定して表示用の文字列を返す
    引数 p1, p2：キャラ
    戻り値：結果の文字列
    """
    if p1.hp > p2.hp:
        return f"{p1.name} WIN!"
    if p2.hp > p1.hp:
        return f"{p2.name} WIN!"
    return "DRAW"


def create_fighters() -> tuple[Fighter, Fighter]:
    """
    2人のキャラを初期状態で生成する
    """
    p1 = Fighter("P1", 250, 1, P1_KEYS, "fig/p1.png", (60, 120, 255))
    p2 = Fighter("P2", 750, -1, P2_KEYS, "fig/p2.png", (255, 80, 80))
    return p1, p2


def main() -> None:
    pg.display.set_caption("2D格闘ゲーム（仮）")
    screen = pg.display.set_mode((WIDTH, HEIGHT))
    clock = pg.time.Clock()
    font_s = pg.font.Font(None, 36)
    font_l = pg.font.Font(None, 100)
    bg_img = pg.image.load("fig/bg.png").convert() if os.path.exists("fig/bg.png") else None

    p1, p2 = create_fighters()
    tmr = 0  # 経過フレーム数
    result = ""  # 決着時の文字列（空なら対戦中）

    while True:
        for event in pg.event.get():
            if event.type == pg.QUIT:
                return
            if event.type == pg.KEYDOWN and event.key == pg.K_ESCAPE:
                return
            if event.type == pg.KEYDOWN and event.key == pg.K_r and result:
                p1, p2 = create_fighters()  # リスタート
                tmr = 0
                result = ""

        if not result:  # 対戦中の処理
            key_lst = pg.key.get_pressed()
            p1.handle_input(key_lst)
            p2.handle_input(key_lst)
            p1.update()
            p2.update()
            push_apart(p1, p2)
            p1.face_to(p2)
            p2.face_to(p1)
            check_hit(p1, p2)
            check_hit(p2, p1)
            tmr += 1
            remain = ROUND_TIME - tmr // FPS
            if p1.hp <= 0 or p2.hp <= 0 or remain <= 0:
                result = judge_winner(p1, p2)

        # 描画
        if bg_img is not None:
            screen.blit(bg_img, (0, 0))
        else:
            screen.fill((30, 30, 50))
            pg.draw.rect(screen, (90, 70, 50), (0, GROUND_Y, WIDTH, HEIGHT - GROUND_Y))
        p1.draw(screen)
        p2.draw(screen)
        draw_hp_bar(screen, p1, 40, font_s)
        draw_hp_bar(screen, p2, WIDTH - 440, font_s)
        remain = max(0, ROUND_TIME - tmr // FPS)
        draw_center_text(screen, str(remain), font_s, 32)
        if result:
            draw_center_text(screen, result, font_l, HEIGHT // 2 - 40)
            draw_center_text(screen, "R: Restart  /  Esc: Quit", font_s, HEIGHT // 2 + 30)
        pg.display.update()
        clock.tick(FPS)


if __name__ == "__main__":
    pg.init()
    main()
    pg.quit()
    sys.exit()