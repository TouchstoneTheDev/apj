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
            gravity: { y: 400 }, // Side-scrolling gravity
            debug: false
        }
    }
};

const game = new Phaser.Game(config);

function preload() {
    this.load.spritesheet('porter', 'assets/porter.png', { frameWidth: 32, frameHeight: 48 });
}

function create() {
    // --- Kitchen Environment ---
    this.cameras.main.setBackgroundColor('#D3D3D3'); // Light grey background

    // Create a group for all platforms for cleaner collision detection
    const platforms = this.physics.add.staticGroup();

    // Main floor
    platforms.create(400, 580, 'ground').setScale(2).refreshBody(); // We'll create a 'ground' texture

    // Kitchen platforms and shelves
    platforms.create(600, 400, 'platform'); // A platform for the sink
    platforms.create(150, 450, 'platform');   // A platform for the dish pile
    platforms.create(750, 220, 'platform'); // A platform for the drying rack

    // Decorative elements
    this.add.rectangle(100, 100, 80, 120, 0xADD8E6); // Window
    this.add.rectangle(700, 100, 80, 120, 0xADD8E6); // Window
    this.add.rectangle(400, 150, 200, 20, 0x8B4513); // Shelf

    // Entrance (visual only)
    this.add.rectangle(20, 500, 40, 150, 0x654321);

    // --- Placeholder Textures ---
    // We'll create these textures dynamically for now
    const graphics = this.add.graphics();
    graphics.fillStyle(0x663300, 1);
    graphics.fillRect(0, 0, 400, 32);
    graphics.generateTexture('ground', 400, 32);

    graphics.fillStyle(0xA0522D, 1);
    graphics.fillRect(0, 0, 200, 32);
    graphics.generateTexture('platform', 200, 32);

    // Easter Egg Textures
    graphics.fillStyle(0xFFC0CB, 1); // Pink for the wig
    graphics.fillEllipse(30, 20, 60, 40);
    graphics.generateTexture('wig', 60, 40);

    graphics.fillStyle(0xFFFF00, 1); // Yellow for the topa
    graphics.fillTriangle(0, 50, 25, 0, 50, 50);
    graphics.generateTexture('topa', 50, 50);

    // Sparkle particle texture
    graphics.fillStyle(0xffffff, 1);
    graphics.fillCircle(5, 5, 5);
    graphics.generateTexture('sparkle', 10, 10);
    graphics.destroy();

    // --- Player ---
    this.player = this.physics.add.sprite(100, 450, 'porter');
    this.player.setBounce(0.2);
    this.player.setCollideWorldBounds(true);
    this.physics.add.collider(this.player, platforms);

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

    // --- Particle Emitter for Sparkles ---
    this.emitter = this.add.particles('sparkle').createEmitter({
        speed: 100,
        scale: { start: 1, end: 0 },
        blendMode: 'ADD',
        lifespan: 600,
        on: false // Don't start emitting right away
    });

    // We'll store these to use in the gameplay implementation
    this.cursors = this.input.keyboard.createCursorKeys();


    // --- Interaction Zones (will be defined later) ---

    // --- Easter Egg Implementation ---
    const wig = this.add.sprite(400, 130, 'wig').setInteractive(); // Place the wig on the shelf
    const topa = this.add.sprite(400, 90, 'topa').setVisible(false);

    wig.on('pointerdown', () => {
        topa.setVisible(true);
        // Optional: Hide the wig after a click
        wig.setVisible(false);
    });
}

function update() {
    // --- Player Movement ---
    if (this.cursors.left.isDown) {
        this.player.setVelocityX(-160);
        this.player.anims.play('left', true);
    } else if (this.cursors.right.isDown) {
        this.player.setVelocityX(160);
        this.player.anims.play('right', true);
    } else {
        this.player.setVelocityX(0);
        this.player.anims.play('turn');
    }

    if (this.cursors.up.isDown && this.player.body.touching.down) {
        this.player.setVelocityY(-330);
    }
}