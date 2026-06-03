// SdkConfigOverride.h — Force-undefines the Arduino framework's sdkconfig.h
// defaults that are too large for our application, then sets memory-efficient
// values. Must be force-included via -include before any other header.
//
// The sdkconfig.h included by NimBLE-Arduino's nimconfig.h defines many
// CONFIG_BT_NIMBLE_* values without #ifndef guards. Our build_flags -D
// values are set first, but these #define directives override them.
// This header clears them first, then applies our values.

// Clear NimBLE sdkconfig defaults that waste DRAM
#undef CONFIG_BT_NIMBLE_MAX_CONNECTIONS
#undef CONFIG_BT_NIMBLE_MSYS1_BLOCK_COUNT
#undef CONFIG_BT_NIMBLE_MAX_BONDS
#undef CONFIG_BT_NIMBLE_MSYS_1_BLOCK_COUNT
#undef CONFIG_BT_NIMBLE_MSYS_2_BLOCK_COUNT
#undef CONFIG_BT_NIMBLE_TRANSPORT_ACL_FROM_LL_COUNT
#undef CONFIG_BT_NIMBLE_TRANSPORT_ACL_SIZE

// Our memory-efficient values
#define CONFIG_BT_NIMBLE_MAX_CONNECTIONS 1
#define CONFIG_BT_NIMBLE_MSYS1_BLOCK_COUNT 4
#define CONFIG_BT_NIMBLE_MAX_BONDS 0
#define CONFIG_BT_NIMBLE_MSYS_1_BLOCK_COUNT 4
#define CONFIG_BT_NIMBLE_MSYS_2_BLOCK_COUNT 2
#define CONFIG_BT_NIMBLE_TRANSPORT_ACL_FROM_LL_COUNT 4
#define CONFIG_BT_NIMBLE_TRANSPORT_ACL_SIZE 128
