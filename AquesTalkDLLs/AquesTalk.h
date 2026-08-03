//////////////////////////////////////////////////////////////////////
/*!	@class	AquesTalk1

	@brief	規則音声合成エンジン AquesTalk1

  音声記号列から音声波形データをメモリ上に生成する
  出力音声波形は、8HKzサンプリング, 16bit,モノラル,WAVフォーマット


	@author	AQUEST Corp.

	@date	2006/05/08	Creation
	@date	2020/11/19	Ver.1.7
	@date	2025/04/01	Ver.2.0 EUC,Roman入力の削除。ライセンスキー関数追加
*/
//  COPYRIGHT (C) 2006- AQUEST CORP.
//////////////////////////////////////////////////////////////////////
#pragma once
#ifdef __cplusplus
extern "C"{
#endif

/////////////////////////////////////////////
//!	音声記号列から音声波形を生成
//!	音声波形データは内部で領域確保される。
//!	音声波形データの解放は本関数の呼び出し側でAquesTalk_FreeWave()にて行う
//! @param	iSpeed[in]	発話速度 [%] 50-300 の間で指定
//!	@param	pSize[out]	生成した音声データのサイズ[byte]（エラーの場合はエラーコードが返る）
//!	@return	WAVフォーマットの音声データの先頭アドレス。エラー時はNULLが返る

//! @param	koe[in]		音声記号列（SJIS NULL終端）
unsigned char * __stdcall AquesTalk_Synthe(const char *koe, int iSpeed, int *pSize);

//! @param	koe[in]		音声記号列（UTF8 NULL終端 BOMはつけられない）
unsigned char * __stdcall AquesTalk_Synthe_Utf8(const char *koe, int iSpeed, int *pSize);

//! @param	koe[in]		音声記号列（UTF16 NULL終端 BOMの有無は問わない　エンディアンは実行環境に従う）
unsigned char * __stdcall AquesTalk_Synthe_Utf16(const unsigned short *koe, int iSpeed, int *pSize);

/////////////////////////////////////////////
//!	音声データの領域を開放
//!	@param  wav[in]		AquesTalk_Synthe()で返されたアドレスを指定
void __stdcall AquesTalk_FreeWave(unsigned char *wav);

/////////////////////////////////////////////
//!	開発ライセンスキー設定
//!	音声波形を生成する前に一度呼び出す。
//!	これにより評価版の制限がなくなる。
//!	@param  key[in]		ライセンスキーを指定
//!	@return	ライセンスキーが正しければ0、正しくなければ1が返る
//! *キーの解析を防ぐため不正なキーでも0を返す場合がある。このとき制限は解除されない。
int __stdcall AquesTalk_SetDevKey(const char* key);

/////////////////////////////////////////////
//!	使用ライセンスキー設定
//!	音声波形を生成する前に一度呼び出す。
//!	以降、合成音声データに含まれる透かしが、使用ライセンス無しから取得済みに変化する
//!	@param  key[in]		ライセンスキーを指定
//!	@return	ライセンスキーが正しければ0、正しくなければ1が返る
//! *キーの解析を防ぐため不正なキーでも0を返す場合がある。この場合、ライセンス無のままである。
int __stdcall AquesTalk_SetUsrKey(const char* key);

#ifdef __cplusplus
}
#endif
//  ----------------------------------------------------------------------
// !  Copyright AQUEST Corp. 2006- .  All Rights Reserved.                !
// !  An unpublished and CONFIDENTIAL work.  Reproduction, adaptation, or !
// !  translation without prior written permission is prohibited except   !
// !  as allowed under the copyright laws.                                !
//  ----------------------------------------------------------------------
