#ifndef _XSAT_VERIFY_H_
#define _XSAT_VERIFY_H_

#include <stdbool.h>
#include <stdio.h>

double DLE(double x,double y);
double DLT(double x,double y);
double DGT(double x,double y);
double DGE(double x,double y);
double DEQ(double x,double y);
double DNE(double x,double y);

double DLE_f32(float x, float y);
double DLT_f32(float x, float y);
double DGT_f32(float x, float y);
double DGE_f32(float x, float y);
double DEQ_f32(float x, float y);
double DNE_f32(float x, float y);

double  DCONST(double c);
double BAND(double x,double y);
double BOR(double x,double y);
float TR32(double x);
//double  BAND(bool x,bool y);
//bool  BOR(bool x,bool y);
double MAX(double a, double b);

double DLE(double x,double y){
    return 1.0-(x<=y);
}

double DLE_f32(float x, float y){
    return 1.0-(x<=y);
}

double DLT(double x,double y){
    return 1.0-(x<y);
}

double DLT_f32(float x, float y){
    return 1.0-(x<y);
}

double DGE(double x,double y)  {
     return  1.0-(x>=y);
}

double DGE_f32(float x, float y)  {
     return  1.0-(x>=y);
}

double DGT(double x,double y)  {
      return 1.0-(x>y);
}

double DGT_f32(float x,float y)  {
      return 1.0-(x>y);
}

double DEQ(double x, double y){
    return  1.0-(x==y);
}

double DEQ_f32(float x, float y){
    return  1.0-(x==y);
}

double DNE(double x,double y) {
    return  1.0-(x!=y);
}

double DNE_f32(float x,float y) {
    return  1.0-(x!=y);
}

double  BAND(double x,double y){
  if (x==0 && y ==0) return 0;
  else return 1.0;

}

double  BOR(double x,double y){
   if (x==0 || y ==0) return 0;
  else return 1.0;
}

double DCONST(double c){return c;}
float TR32(double x){
  return (float)x;
}

double MAX(double a, double b) {
  return (((a) > (b)) ? (a) : (b));
}


#endif
