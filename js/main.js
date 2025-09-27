const config = {
    type: Phaser.AUTO,
    width: 800,
    height: 600,
    scene: {
        preload: preload,
        create: create,
        update: update
    },
    physics: {
        default: 'arcade',
        arcade: {
            debug: false
        }
    }
};

const game = new Phaser.Game(config);

let player;
let cursors;
let dirtyDishPile;
let sink;
let carriedDish = null;
let washTimer = null;
let instructionText;

function preload() {
    this.load.spritesheet('porter', 'assets/porter.png', { frameWidth: 32, frameHeight: 48 });
    this.load.image('dirty-dish', 'assets/dirty-dish.png');
    this.load.image('dish', 'assets/dish.png');
}

function create() {
    this.cameras.main.setBackgroundColor('#cccccc');

    const ground = this.add.rectangle(400, 580, 800, 40, 0x663300);
    this.physics.add.existing(ground, true);

    dirtyDishPile = this.add.rectangle(100, 540, 100, 80, 0x00ff00);
    sink = this.add.rectangle(700, 540, 100, 80, 0x0000ff);
    this.add.sprite(100, 540, 'dirty-dish');

    player = this.physics.add.sprite(200, 450, 'porter');
    player.setBounce(0.2);
    player.setCollideWorldBounds(true);
    this.physics.add.collider(player, ground);

    this.anims.create({
        key: 'left',
        frames: this.anims.generateFrameNumbers('porter', { start: 0, end: 3 }),
        frameRate: 10,
        repeat: -1
    });

    this.anims.create({
        key: 'turn',
        frames: [ { key: 'porter', frame: 4 } ],
        frameRate: 20
    });

    this.anims.create({
        key: 'right',
        frames: this.anims.generateFrameNumbers('porter', { start: 5, end: 8 }),
        frameRate: 10,
        repeat: -1
    });

    cursors = this.input.keyboard.createCursorKeys();

    instructionText = this.add.text(16, 16, 'Walk to the green area and press SPACE to pick up a dish.', { fontSize: '18px', fill: '#000' });
}

function update() {
    if (cursors.left.isDown) {
        player.setVelocityX(-160);
        player.anims.play('left', true);
    } else if (cursors.right.isDown) {
        player.setVelocityX(160);
        player.anims.play('right', true);
    } else {
        player.setVelocityX(0);
        player.anims.play('turn');
    }

    if (cursors.up.isDown && player.body.touching.down) {
        player.setVelocityY(-330);
    }

    // Interaction logic
    const spaceJustPressed = Phaser.Input.Keyboard.JustDown(cursors.space);
    const playerBounds = player.getBounds();
    const dirtyDishPileBounds = dirtyDishPile.getBounds();
    const sinkBounds = sink.getBounds();

    if (spaceJustPressed) {
        if (!carriedDish && Phaser.Geom.Intersects.RectangleToRectangle(playerBounds, dirtyDishPileBounds)) {
            // Pick up dish
            carriedDish = this.add.sprite(player.x, player.y - 50, 'dirty-dish');
            instructionText.setText('Carry the dish to the blue sink and press SPACE to wash.');
        } else if (carriedDish && carriedDish.texture.key === 'dirty-dish' && Phaser.Geom.Intersects.RectangleToRectangle(playerBounds, sinkBounds)) {
            // Wash dish
            instructionText.setText('Washing...');
            if (washTimer) {
                washTimer.remove();
            }
            washTimer = this.time.addEvent({
                delay: 2000, // 2 seconds to wash
                callback: () => {
                    carriedDish.setTexture('dish');
                    instructionText.setText('Dish is clean! Carry it back to the green area.');
                },
                callbackScope: this
            });
        } else if (carriedDish && carriedDish.texture.key === 'dish' && Phaser.Geom.Intersects.RectangleToRectangle(playerBounds, dirtyDishPileBounds)) {
            // Drop off clean dish
            carriedDish.destroy();
            carriedDish = null;
            instructionText.setText('Good job! Another dirty dish has appeared.');
            // For now, we just reset
        }
    }

    if (carriedDish) {
        carriedDish.x = player.x;
        carriedDish.y = player.y - 50;
    }
}